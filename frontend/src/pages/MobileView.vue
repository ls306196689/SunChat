<script setup>
// R-014: 局域网移动会话页(轻量单栏)。复用 chat store(streamChat/sendMessage/会话)
// 与 request.js 上传封装(uploadChatImage/uploadVideoFrames/transcribeSpeech/speechStatus)。
import { ref, nextTick, onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import {
  uploadChatImage, uploadVideoFrames, transcribeSpeech, speechStatus, chatImageUrl
} from '@/utils/request'

const chatStore = useChatStore()
const input = ref('')
const sending = ref(false)
const errMsg = ref('')
const listEl = ref(null)
const imgInput = ref(null)

// 待发附件(轻量版:本地预览 + 上传态,失败整项重试不占额度)
const pending = ref([])   // {kind:'image'|'video', localUrl, id?, status:'uploading'|'done'|'error', file}
const MAX_IMAGES = 4

// 语音
const micSupported = ref(true)
const recording = ref(false)
const transcribing = ref(false)
const audioInput = ref(null)
let recorder = null
let audioChunks = []

onMounted(async () => {
  micSupported.value = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)
  try {
    await chatStore.fetchSessions()
    if (chatStore.sessions.length) await chatStore.switchSession(chatStore.sessions[0].session_id)
    else await chatStore.createSession()
  } catch { /* store 已置 error */ }
})

function scrollBottom() {
  nextTick(() => { if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight })
}

async function onPickImages(e) {
  const files = Array.from(e.target.files || [])
  e.target.value = ''
  for (const f of files) {
    if (pending.value.filter(p => p.kind === 'image').length >= MAX_IMAGES) break
    await attachAndUpload(f, 'image')
  }
}
async function onPickVideo(e) {
  const files = Array.from(e.target.files || [])
  e.target.value = ''
  for (const f of files) await attachAndUpload(f, 'video')
}

async function attachAndUpload(file, kind) {
  const item = { kind, localUrl: URL.createObjectURL(file), file, status: 'uploading', ids: [], error: '' }
  pending.value.push(item)
  try {
    if (kind === 'image') {
      const r = await uploadChatImage(file)
      const id = r?.data?.data?.image_id ?? r?.data?.image_id ?? r?.image_id  // R-012 双写防御
      if (!id) throw new Error('响应缺少 image_id')
      item.ids = [id]
    } else {
      const r = await uploadVideoFrames(file)
      const ids = r?.data?.data?.frame_ids ?? r?.data?.frame_ids ?? r?.frame_ids
      if (!ids || !ids.length) throw new Error('未解出帧')
      item.ids = ids
    }
    item.status = 'done'
  } catch (err) {
    item.status = 'error'
    item.error = err.response?.data?.detail || err.message
  }
}

function removePending(i) {
  URL.revokeObjectURL(pending.value[i].localUrl)
  pending.value.splice(i, 1)
}
async function retryPending(i) {
  const item = pending.value[i]
  item.status = 'uploading'; item.error = ''
  try {
    if (item.kind === 'image') {
      const r = await uploadChatImage(item.file)
      const id = r?.data?.data?.image_id ?? r?.data?.image_id ?? r?.image_id
      if (!id) throw new Error('响应缺少 image_id')
      item.ids = [id]
    } else {
      const r = await uploadVideoFrames(item.file)
      const ids = r?.data?.data?.frame_ids ?? r?.data?.frame_ids ?? r?.frame_ids
      if (!ids || !ids.length) throw new Error('未解出帧')
      item.ids = ids
    }
    item.status = 'done'
  } catch (err) {
    item.status = 'error'
    item.error = err.response?.data?.detail || err.message
  }
}

async function send() {
  const text = input.value.trim()
  const imgs = pending.value.filter(p => p.status === 'done').flatMap(p => p.ids)
  const uploading = pending.value.some(p => p.status === 'uploading')
  if (!text && !imgs.length) return
  if (uploading) { errMsg.value = '附件上传中,请稍候'; return }
  errMsg.value = ''
  input.value = ''
  pending.value.forEach(p => URL.revokeObjectURL(p.localUrl))
  pending.value = []
  sending.value = true
  scrollBottom()
  try {
    await chatStore.sendMessage(text || '请描述这些图片', true, true, imgs)
  } catch (err) {
    errMsg.value = err?.response?.data?.detail || err?.message || '发送失败'
  } finally {
    sending.value = false
    scrollBottom()
  }
}

// ===== 语音(双路:D-142 getUserMedia 可用则录,否则文件兜底) =====
async function toggleMic() {
  if (recording.value) { recorder && recorder.stop(); return }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    recorder = new MediaRecorder(stream)
    audioChunks = []
    recorder.ondataavailable = (e) => { if (e.data && e.data.size) audioChunks.push(e.data) }
    recorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop())
      recording.value = false
      const blob = new Blob(audioChunks, { type: recorder.mimeType || 'audio/webm' })
      audioChunks = []
      if (blob.size) await doTranscribe(blob)
    }
    recorder.start()
    recording.value = true
  } catch {
    micSupported.value = false
    errMsg.value = '麦克风不可用(非HTTPS禁麦),请用下方"音频文件"'
  }
}
async function onPickAudio(e) {
  const f = (e.target.files || [])[0]
  e.target.value = ''
  if (f) await doTranscribe(f)
}
async function doTranscribe(blobOrFile) {
  transcribing.value = true
  try {
    const r = await transcribeSpeech(blobOrFile)
    const t = ((r?.data?.text ?? r?.text) || '').trim()
    if (t) input.value = input.value.trim() ? input.value.trimEnd() + ' ' + t : t
    else errMsg.value = '未识别到语音内容'
  } catch (err) {
    errMsg.value = '转写失败: ' + (err.response?.data?.detail || err.message)
  } finally { transcribing.value = false }
}

async function newSession() {
  await chatStore.createSession()
}
</script>

<template>
  <div class="mv">
    <header class="mv-bar">
      <span class="mv-title">SunChat</span>
      <select class="mv-sel" :value="chatStore.currentSession?.session_id"
              @change="chatStore.switchSession($event.target.value); scrollBottom()">
        <option v-for="s in chatStore.sessions" :key="s.session_id" :value="s.session_id">
          {{ s.title || ('会话 ' + s.session_id) }}
        </option>
      </select>
      <button class="mv-btn" @click="newSession">+新对话</button>
    </header>

    <main ref="listEl" class="mv-list">
      <div v-for="m in chatStore.messages" :key="m.id" :class="['mv-row', m.role]">
        <div class="mv-bub">
          <div v-if="m.images && m.images.length" class="mv-imgs">
            <img v-for="iid in m.images" :key="iid" :src="chatImageUrl(iid)" loading="lazy" alt="图" />
          </div>
          <span class="mv-text">{{ m.content }}</span>
          <span v-if="m.role === 'assistant' && chatStore.loading && !m.content" class="mv-dots">…</span>
        </div>
      </div>
    </main>

    <div v-if="pending.length" class="mv-pend">
      <div v-for="(p, i) in pending" :key="i" class="mv-pitem">
        <img :src="p.localUrl" :alt="p.kind" />
        <span v-if="p.status === 'uploading'" class="mv-spin">上传中…</span>
        <button v-else-if="p.status === 'error'" class="mv-retry" @click="retryPending(i)">重试</button>
        <button class="mv-x" @click="removePending(i)">×</button>
        <div v-if="p.error" class="mv-perr">{{ p.error }}</div>
      </div>
    </div>
    <p v-if="errMsg" class="mv-err">{{ errMsg }}</p>

    <footer class="mv-in">
      <button class="mv-btn" :disabled="transcribing" @click="imgInput.click()">相册</button>
      <input ref="imgInput" type="file" accept="image/*" multiple hidden @change="onPickImages" />
      <button class="mv-btn" :disabled="transcribing" @click="$refs.videoInput.click()">视频</button>
      <input ref="videoInput" type="file" accept="video/*" hidden @change="onPickVideo" />
      <button v-if="micSupported" class="mv-btn" :class="{ rec: recording }"
              :disabled="transcribing" @click="toggleMic">{{ recording ? '停止' : '麦克风' }}</button>
      <button v-else class="mv-btn" @click="$refs.audioInput.click()">音频文件</button>
      <input ref="audioInput" type="file" accept="audio/*" hidden @change="onPickAudio" />
      <textarea v-model="input" rows="1" placeholder="与助手 conversation…" @keydown.enter.exact.prevent="send" />
      <button class="mv-send" :disabled="sending || transcribing" @click="send">{{ sending ? '…' : '发送' }}</button>
    </footer>
  </div>
</template>

<style scoped>
.mv { display: flex; flex-direction: column; height: 100dvh; background: #f5f6f8; }
.mv-bar { display: flex; gap: 8px; align-items: center; padding: 10px 12px; background: #fff; border-bottom: 1px solid #e5e7eb; }
.mv-title { font-weight: 700; }
.mv-sel { flex: 1; min-width: 0; padding: 6px; border: 1px solid #d1d5db; border-radius: 8px; background: #fff; }
.mv-list { flex: 1; overflow-y: auto; padding: 12px; }
.mv-row { display: flex; margin-bottom: 10px; }
.mv-row.user { justify-content: flex-end; }
.mv-row.assistant { justify-content: flex-start; }
.mv-bub { max-width: 82%; padding: 9px 12px; border-radius: 14px; background: #fff; border: 1px solid #e5e7eb; word-break: break-word; }
.mv-row.user .mv-bub { background: #2563eb; color: #fff; border-color: #2563eb; }
.mv-imgs { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 4px; }
.mv-imgs img { max-width: 140px; max-height: 140px; border-radius: 8px; object-fit: cover; }
.mv-text { white-space: pre-wrap; }
.mv-pend { display: flex; gap: 8px; overflow-x: auto; padding: 6px 12px; background: #fff; border-top: 1px solid #e5e7eb; }
.mv-pitem { position: relative; flex: 0 0 auto; }
.mv-pitem img { width: 56px; height: 56px; object-fit: cover; border-radius: 8px; }
.mv-spin, .mv-retry { position: absolute; bottom: 2px; left: 2px; font-size: 11px; background: rgba(0,0,0,.6); color: #fff; padding: 1px 5px; border-radius: 6px; border: none; }
.mv-x { position: absolute; top: -6px; right: -6px; width: 20px; height: 20px; border-radius: 50%; border: none; background: #1118; color: #fff; }
.mv-perr { font-size: 11px; color: #dc2626; max-width: 70px; }
.mv-err { margin: 0 12px; padding: 4px 8px; font-size: 12px; color: #dc2626; background: #fef2f2; border-radius: 6px; }
.mv-in { display: flex; gap: 6px; align-items: flex-end; padding: 8px 10px calc(8px + env(safe-area-inset-bottom)); background: #fff; border-top: 1px solid #e5e7eb; }
.mv-in textarea { flex: 1; resize: none; padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 10px; font-size: 15px; max-height: 96px; }
.mv-btn { padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 10px; background: #f9fafb; font-size: 13px; }
.mv-btn.rec { background: #fee2e2; border-color: #dc2626; color: #b91c1c; }
.mv-send { padding: 8px 14px; border: none; border-radius: 10px; background: #2563eb; color: #fff; font-size: 15px; }
</style>
