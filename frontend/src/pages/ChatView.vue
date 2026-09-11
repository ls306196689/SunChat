<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch, reactive } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useMemoryStore } from '@/stores/memory'
import { useThemeStore } from '@/stores/theme'
import { useMessageInput } from '@/composables/useMessageInput'
import MessageItem from '@/components/ui/MessageItem.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import SessionItem from '@/components/ui/SessionItem.vue'
import { NInput, NButton, NSpace, NScrollbar, NModal, NButtonGroup } from 'naive-ui'
import { marked } from 'marked'
import { uploadChatImage, chatImageUrl, transcribeSpeech, speechStatus, uploadVideoFrames } from '@/utils/request'

const chatStore = useChatStore()
const memoryStore = useMemoryStore()
const themeStore = useThemeStore()

const inputRef = ref(null)
const scrollContainerRef = ref(null)
const showSessionList = ref(false)

const inputContent = ref('')
// R-008/R-011: 待发送图片状态机 [{ id, url, localUrl, name, status: uploading|done|error, error, rawFile }]
const pendingImages = ref([])
const imageInputRef = ref(null)
const MAX_CHAT_IMAGES = 4
const MAX_CHAT_IMAGE_MB = 8
const memoryEnabled = ref(true)
const searchEnabled = ref(true)
const showSentMessages = ref(false)
const message = window.message || { error: (msg) => console.error(msg), success: (msg) => console.log(msg), warning: (msg) => console.warn(msg) }

// 获取所有用户发送的内容
const userSentMessages = computed(() => {
  return chatStore.messages.filter(msg => msg.role === 'user' && msg.content.trim())
})

// 自动滚动到底部
function scrollToBottom() {
  nextTick(() => {
    const container = scrollContainerRef.value?.$el
    if (container) {
      container.scrollTop = container.scrollHeight
    }
  })
}

// 输入框行为控制
const { handleKeyDown, isEnterWithoutShift, handleEnterSend } = useMessageInput(inputRef, () => handleSend())

onMounted(() => {
  chatStore.fetchSessions()
  memoryStore.fetchStats()
  nextTick(() => {
    scrollToBottom()
  })
})

// 自动滚动监听
watch(() => chatStore.messages, () => {
  nextTick(() => {
    scrollToBottom()
  })
}, { deep: true })

// R-011: 图片上传状态机——乐观本地预览(uploading)→ done/error(可重试)
function revokeEntry(entry) {
  if (entry && entry.localUrl) {
    try { URL.revokeObjectURL(entry.localUrl) } catch (e) { /* noop */ }
    entry.localUrl = null
  }
}

function uploadEntry(entry) {
  entry.status = 'uploading'
  entry.error = null
  return uploadChatImage(entry.rawFile)
    .then(resp => {
      const imageId = resp?.data?.image_id ?? resp?.image_id  // R-012: 拦截器已解包一层
      if (!imageId) throw new Error('上传返回异常')
      entry.id = imageId
      entry.url = chatImageUrl(imageId)
      entry.status = 'done'
    })
    .catch(err => {
      entry.status = 'error'
      entry.error = err?.response?.data?.detail || err.message || '上传失败'
    })
}

function addImageFiles(files) {
  for (const file of files) {
    if (!file || !file.type || !file.type.startsWith('image/')) continue
    if (file.size > MAX_CHAT_IMAGE_MB * 1024 * 1024) {
      message.error(`图片超过 ${MAX_CHAT_IMAGE_MB}MB 限制: ${file.name}`)
      continue
    }
    if (pendingImages.value.length >= MAX_CHAT_IMAGES) {
      message.error(`单条消息最多 ${MAX_CHAT_IMAGES} 张图`)
      break
    }
    const entry = reactive({
      id: null,
      url: null,
      localUrl: URL.createObjectURL(file),  // 乐观预览,不等服务器
      name: file.name || '图片',
      status: 'uploading',
      error: null,
      rawFile: file
    })
    pendingImages.value.push(entry)
    uploadEntry(entry)
  }
}

function retryUpload(i) {
  const entry = pendingImages.value[i]
  if (entry && entry.status === 'error' && entry.rawFile) uploadEntry(entry)
}

const pendingDoneCount = computed(() =>
  pendingImages.value.filter(p => p.status === 'done').length)
const pendingUploading = computed(() =>
  pendingImages.value.some(p => p.status === 'uploading'))

function openImagePicker() {
  imageInputRef.value && imageInputRef.value.click()
}

// ==================== R-010: 视频输入(抽帧复用图片通道) ====================
const videoInputRef = ref(null)
const MAX_VIDEO_MB = 50
const extractingVideo = ref(false)

function openVideoPicker() {
  videoInputRef.value && videoInputRef.value.click()
}

async function onVideoSelected(e) {
  const file = e.target.files && e.target.files[0]
  e.target.value = ''
  if (!file) return
  if (file.size > MAX_VIDEO_MB * 1024 * 1024) {
    message.error(`视频超过 ${MAX_VIDEO_MB}MB 限制: ${file.name}`)
    return
  }
  extractingVideo.value = true
  try {
    const resp = await uploadVideoFrames(file)
    const d = resp?.data ?? resp  // R-012: 拦截器已解包,双读防御
    const ids = d?.frame_ids || []
    if (!ids.length) throw new Error('未能从视频提取画面')
    let added = 0
    for (const id of ids) {
      if (pendingImages.value.length >= MAX_CHAT_IMAGES) {
        message.warning(`已达 ${MAX_CHAT_IMAGES} 张上限,未全部添加`)
        break
      }
      pendingImages.value.push({
        id,
        url: chatImageUrl(id),
        localUrl: null,
        name: `帧@${(d.duration||0).toFixed(1)}s`,
        status: 'done',
        error: null,
        rawFile: null
      })
      added += 1
    }
    if (added) message.success(`已提取 ${added} 帧(${(d.duration || 0).toFixed(1)}s 视频)`)
  } catch (err) {
    message.error('视频处理失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    extractingVideo.value = false
  }
}

function onImageSelected(e) {
  addImageFiles([...(e.target.files || [])])
  e.target.value = ''
}

function onPaste(e) {
  const items = e.clipboardData && e.clipboardData.items
  if (!items) return
  const files = []
  for (const item of items) {
    if (item.type && item.type.startsWith('image/')) {
      const f = item.getAsFile()
      if (f) files.push(f)
    }
  }
  if (files.length) {
    e.preventDefault()
    addImageFiles(files)
  }
}

// R-011: 拖拽遮罩(enter/leave 计数防子元素抖动)
const dragDepth = ref(0)
const dragActive = computed(() => dragDepth.value > 0)

function onDragEnter(e) {
  if (e.dataTransfer && [...(e.dataTransfer.types || [])].includes('Files')) {
    e.preventDefault()
    dragDepth.value += 1
  }
}
function onDragOver(e) {
  if (dragActive.value) e.preventDefault()
}
function onDragLeave() {
  if (dragDepth.value > 0) dragDepth.value -= 1
}

function onDrop(e) {
  e.preventDefault()
  dragDepth.value = 0
  if (e.dataTransfer && e.dataTransfer.files) {
    addImageFiles([...e.dataTransfer.files])
  }
}

function removePendingImage(i) {
  revokeEntry(pendingImages.value[i])
  pendingImages.value.splice(i, 1)
}

// ==================== R-009: 语音输入 ====================
const recorderSupported = typeof window !== 'undefined' &&
  typeof window.MediaRecorder !== 'undefined' &&
  !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)
const isRecording = ref(false)
const isTranscribing = ref(false)
const recordSeconds = ref(0)
let mediaRecorder = null
let audioChunks = []
let recordTimer = null

function pickAudioMime() {
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']
  for (const m of candidates) {
    if (window.MediaRecorder.isTypeSupported && window.MediaRecorder.isTypeSupported(m)) return m
  }
  return ''
}

function startRecordTimer() {
  recordSeconds.value = 0
  recordTimer = setInterval(() => { recordSeconds.value += 1 }, 1000)
}

function stopRecordTimer() {
  if (recordTimer) { clearInterval(recordTimer); recordTimer = null }
}

async function startRecording() {
  if (isRecording.value || chatStore.loading) return
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const mime = pickAudioMime()
    mediaRecorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined)
    audioChunks = []
    mediaRecorder.ondataavailable = (e) => { if (e.data && e.data.size) audioChunks.push(e.data) }
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop())
      const blobType = mediaRecorder.mimeType || mime || 'audio/webm'
      const blob = new Blob(audioChunks, { type: blobType })
      audioChunks = []
      if (!blob.size) return
      isTranscribing.value = true
      try {
        const resp = await transcribeSpeech(blob)
        const text = ((resp?.data?.text ?? resp?.text) || '').trim()  // R-012
        if (text) {
          inputContent.value = inputContent.value.trim()
            ? inputContent.value.trimEnd() + ' ' + text
            : text
          inputRef.value && inputRef.value.focus && inputRef.value.focus()
        } else {
          message.warning('未识别到语音内容')
        }
      } catch (err) {
        message.error('语音转写失败: ' + (err.response?.data?.detail || err.message))
      } finally {
        isTranscribing.value = false
      }
    }
    mediaRecorder.start()
    isRecording.value = true
    startRecordTimer()
  } catch (err) {
    message.error('无法访问麦克风: ' + (err.message || '权限被拒绝'))
  }
}

function stopRecording() {
  if (mediaRecorder && isRecording.value) {
    mediaRecorder.stop()
    isRecording.value = false
    stopRecordTimer()
  }
}

onMounted(() => {
  // R-009: ASR 状态探测(仅提示,不阻断;首次转写触发模型加载)
  if (recorderSupported) {
    speechStatus().then(r => {
      const st = r?.data?.status ?? r?.status  // R-012
      if (st === 'unavailable') {
        message.warning('语音模型未预置,🎤 暂不可用')
      }
    }).catch(() => {})
  }
})

// R-011: 组件卸载回收 objectURL,防内存泄漏
onUnmounted(() => {
  pendingImages.value.forEach(revokeEntry)
  stopRecordTimer()
})

async function handleSend() {
  // 空内容或上一条仍在生成时不重复发送（R-008: 有图无字也可发送）
  if ((!inputContent.value.trim() && !pendingImages.value.length) || chatStore.loading) return

  // R-011: 发送策略——uploading 拦截;error 剔除(明示);仅 done 图发送
  if (pendingUploading.value) {
    message.warning('图片上传中,请稍候…')
    return
  }
  const failedCount = pendingImages.value.filter(p => p.status === 'error').length
  if (failedCount && !pendingDoneCount.value && !inputContent.value.trim()) {
    message.error(`${failedCount} 张图片上传失败,请重试或移除`)
    return
  }
  if (failedCount) {
    message.warning(`已忽略 ${failedCount} 张上传失败的图片`)
    pendingImages.value.filter(p => p.status === 'error').forEach(revokeEntry)
    pendingImages.value = pendingImages.value.filter(p => p.status !== 'error')
  }

  const content = inputContent.value
  const sentEntries = pendingImages.value.filter(p => p.status === 'done')
  const imageIds = sentEntries.map(p => p.id)
  inputContent.value = ''
  pendingImages.value = []  // 待发区先清空;失败时回滚回填,成功时随消息 URL 展示无需本地 URL

  try {
    await chatStore.sendMessage(
      content || '请看我发送的图片。',
      memoryEnabled.value,
      searchEnabled.value,
      imageIds
    )
    sentEntries.forEach(revokeEntry)  // 发送成功:本地预览 URL 完成使命

    // 自动滚动到底部
    nextTick(() => {
      scrollToBottom()
    })
  } catch (error) {
    if (!inputContent.value) inputContent.value = content
    // R-011: 发送失败回滚图片(done 项已存服务端,直接回填免重传)
    if (!pendingImages.value.length && sentEntries.length) {
      pendingImages.value = sentEntries
    }
    message.error('发送消息失败: ' + (error.message || '未知错误'))
  }
}

// 渲染 Markdown
function renderMarkdown(text) {
  if (!text || typeof text !== 'string') {
    return ''
  }
  return marked(text)
}

// 时间格式化
function formatTime(time) {
  if (!time) return ''
  return new Date(time).toLocaleString('zh-CN')
}

// 复制消息内容
async function copyMessage(text) {
  try {
    await navigator.clipboard.writeText(text)
    message.success('已复制到剪贴板')
  } catch (error) {
    message.error('复制失败')
  }
}

// 处理会话切换
async function handleSessionClick(session) {
  await chatStore.switchSession(session.session_id)
  showSessionList.value = false
  nextTick(() => {
    scrollToBottom()
  })
}

// 会话重命名
async function handleRenameSession(session, title) {
  const ok = await chatStore.renameSession(session.session_id, title)
  if (ok) message.success('已重命名')
  else message.error('重命名失败')
}

// 会话删除
async function handleDeleteSession(session) {
  if (!window.confirm(`删除会话「${session.title}」？`)) return
  const ok = await chatStore.removeSession(session.session_id)
  if (ok) message.success('已删除')
  else message.error('删除失败')
}

// 渲染加载状态
function renderLoadingMessage() {
  return `
    <div class="loading-message">
      <span class="dot"></span>
      <span class="dot"></span>
      <span class="dot"></span>
    </div>
  `
}

// 检查是否为加载中的 AI 消息
function isLoadingMessage(msg) {
  return msg.role === 'assistant' && msg.content === ''
}
</script>

<template>
  <div class="chat-view">
    <!-- 会话列表模态框 -->
    <n-modal
      v-model:show="showSessionList"
      preset="card"
      title="会话列表"
      class="session-modal"
    >
      <div class="session-list-content">
        <n-button type="primary" @click="chatStore.createSession" style="margin-bottom: 16px; width: 100%;">
          + 新建会话
        </n-button>
        
        <div class="session-empty" v-if="chatStore.sessions.length === 0">
          <EmptyState
            title="暂无会话"
            description="点击上方按钮创建新的会话"
            action-text="新建会话"
            @action="chatStore.createSession"
          />
        </div>
        
        <div class="session-list">
          <SessionItem
            v-for="session in chatStore.sessions"
            :key="session.session_id"
            :session="session"
            :active="chatStore.currentSession?.session_id === session.session_id"
            @click="handleSessionClick(session)"
            @rename="(title) => handleRenameSession(session, title)"
            @remove="() => handleDeleteSession(session)"
          />
        </div>
      </div>
    </n-modal>

    <div class="chat-header">
      <n-space align="center" size="large">
        <n-button text @click="showSessionList = true">
          <span class="header-icon">💬</span>
          {{ chatStore.currentSession?.session_id ? chatStore.sessions.find(s => s.session_id === chatStore.currentSession.session_id)?.title || '会话' : '新建会话' }}
        </n-button>
        
        <n-space>
          <n-button
            size="small"
            :type="memoryEnabled ? 'primary' : 'default'"
            @click="memoryEnabled = !memoryEnabled"
          >
            记忆: {{ memoryEnabled ? '开' : '关' }}
          </n-button>
          <n-button
            size="small"
            :type="searchEnabled ? 'primary' : 'default'"
            @click="searchEnabled = !searchEnabled"
          >
            搜索: {{ searchEnabled ? '开' : '关' }}
          </n-button>
        </n-space>

        <n-button text @click="themeStore.toggleTheme" class="theme-toggle">
          {{ themeStore.isDark ? '🌞' : '🌙' }}
        </n-button>
        <n-button text @click="showSentMessages = true" class="sent-messages-toggle">
          <span class="header-icon">📝</span>
          <span>发送记录</span>
        </n-button>
      </n-space>
    </div>

    <div class="chat-container">
      <n-list class="message-list-wrapper">
        <div
          ref="scrollContainerRef"
          class="message-list"
        >
          <EmptyState
            v-if="chatStore.messages.length === 0"
            icon="👋"
            title="你好！我是你的 AI 助手"
            :description="chatStore.loading ? '正在准备中...' : '开始聊天，我会记住我们之间的对话'"
            :action-text="chatStore.loading ? '' : '发送第一条消息'"
            @action="showSessionList = true"
          />
          
          <div v-else class="message-list-content">
            <MessageItem
              v-for="msg in chatStore.messages"
              :key="msg.id"
              :role="msg.role"
              :content="msg.content"
              :create-time="msg.created_at"
              :sources="msg.sources || []"
              :images="msg.images || []"
              :loading="msg.role === 'assistant' && chatStore.loading && msg.id === (chatStore.messages[chatStore.messages.length - 1]?.id)"
            />
            
          </div>
        </div>
      </n-list>

      <div
        class="input-area"
        :class="{ 'drag-active': dragActive }"
        @drop="onDrop"
        @dragenter="onDragEnter"
        @dragover="onDragOver"
        @dragleave="onDragLeave"
      >
        <!-- R-011: 拖拽遮罩 -->
        <div v-if="dragActive" class="drop-overlay">
          <span class="drop-overlay-icon">🖼️</span>
          <span>松开以添加图片</span>
        </div>
        <!-- R-008: 图片上传(按钮/粘贴/拖拽) -->
        <input
          ref="imageInputRef"
          type="file"
          accept="image/png,image/jpeg,image/gif,image/webp"
          multiple
          style="display: none"
          @change="onImageSelected"
        />
        <input
          ref="videoInputRef"
          type="file"
          accept="video/*"
          style="display: none"
          @change="onVideoSelected"
        />
        <!-- R-011: 待发图三态(上传中/完成/失败重试) + 计数徽章 -->
        <div v-if="pendingImages.length" class="pending-images">
          <span class="pending-counter">{{ pendingImages.length }}/{{ MAX_CHAT_IMAGES }}</span>
          <div
            v-for="(img, i) in pendingImages"
            :key="img.localUrl || img.url || i"
            class="pending-image"
            :class="img.status"
            :title="img.status === 'error' ? ('上传失败: ' + img.error) : img.name"
          >
            <img :src="img.localUrl || img.url" :alt="img.name" />
            <div v-if="img.status === 'uploading'" class="pending-mask">
              <span class="pending-spin"></span>
            </div>
            <div v-else-if="img.status === 'error'" class="pending-mask error">
              <button class="pending-retry" @click.stop="retryUpload(i)" @mousedown.prevent>重试</button>
            </div>
            <button class="pending-remove" title="移除" @click="removePendingImage(i)">×</button>
          </div>
        </div>
        <n-input
          ref="inputRef"
          v-model:value="inputContent"
          type="textarea"
          placeholder="输入消息... (Enter 发送, Shift+Enter 换行, 可粘贴/拖入图片)"
          :autosize="{ minRows: 2, maxRows: 6 }"
          @keydown="handleEnterSend"
          @paste="onPaste"
        />
        
        <div class="input-actions">
          <n-space>
            <n-button
              title="添加图片 (png/jpg/gif/webp, ≤8MB, 最多4张)"
              :disabled="chatStore.loading || pendingImages.length >= 4"
              @click="openImagePicker"
            >
              📎 图片
            </n-button>
            <n-button
              v-if="recorderSupported"
              :type="isRecording ? 'error' : 'default'"
              :loading="isTranscribing"
              :title="isRecording ? `录音中 ${recordSeconds}s,点击停止并转写` : '语音输入 (再次点击停止并转文字)'"
              :disabled="isTranscribing"
              @click="isRecording ? stopRecording() : startRecording()"
            >
              {{ isRecording ? `⏹ ${recordSeconds}s` : '🎤 语音' }}
            </n-button>
            <n-button
              title="视频输入 (mp4/mov/avi/webm, ≤50MB, 自动抽取关键帧)"
              :loading="extractingVideo"
              :disabled="chatStore.loading || extractingVideo || pendingImages.length >= 4"
              @click="openVideoPicker"
            >
              🎬 视频
            </n-button>
            <n-button @click="chatStore.clearMessages" :disabled="chatStore.messages.length === 0">
              清空消息
            </n-button>
            <n-button
              type="primary"
              :loading="chatStore.loading"
              @click="handleSend"
              :disabled="(!inputContent.trim() && !pendingImages.length) || pendingUploading"
            >
              {{ pendingUploading ? '上传中…' : '发送' }}
            </n-button>
          </n-space>
        </div>
      </div>
    </div>

    <!-- 自动滚动按钮 -->
    <div
      v-if="!chatStore.autoLoadMore && chatStore.messages.length > 0"
      class="scroll-to-bottom"
      @click="scrollToBottom"
    >
      <n-button circle type="primary">
        ↓
      </n-button>
    </div>

    <!-- 发送记录模态框 -->
    <n-modal
      v-model:show="showSentMessages"
      preset="card"
      title="发送记录"
      class="sent-messages-modal"
    >
      <div class="sent-messages-content">
        <div class="sent-messages-empty" v-if="userSentMessages.length === 0">
          <EmptyState
            title="暂无发送记录"
            description="发送消息后，它们会在这里显示"
            action-text="开始聊天"
            @action="showSentMessages = false"
          />
        </div>

        <div class="sent-messages-list">
          <div
            v-for="msg in userSentMessages"
            :key="msg.id"
            class="sent-message-item"
          >
            <div class="message-text">{{ msg.content }}</div>
            <div class="message-meta">
              <span>{{ formatTime(msg.created_at) }}</span>
              <n-button
                size="tiny"
                type="primary"
                text
                @click="copyMessage(msg.content)"
              >
                复制
              </n-button>
            </div>
          </div>
        </div>

        <div class="sent-messages-footer">
          <n-button size="small" @click="showSentMessages = false">
            关闭
          </n-button>
        </div>
      </div>
    </n-modal>
  </div>
</template>

<style scoped>
.chat-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #f5f5f5;
}

.chat-header {
  padding: 12px 20px;
  background-color: #fff;
  border-bottom: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.header-icon {
  margin-right: 8px;
}

.theme-toggle {
  font-size: 20px;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.message-list-wrapper {
  flex: 1;
  overflow: hidden;
}

.message-list {
  height: 100%;
  padding: 20px;
  overflow-y: auto;
}

.message-list-content {
  display: flex;
  flex-direction: column;
  padding-bottom: 20px;
}

.input-area {
  position: relative;
  padding: 20px;
  background-color: #fff;
  border-top: 1px solid #eee;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.input-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

/* 加载指示器 */
.loading-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
  gap: 4px;
}

.loading-message {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
  gap: 4px;
}

.dot {
  width: 8px;
  height: 8px;
  background-color: #999;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.dot:nth-child(1) { animation-delay: -0.32s; }
.dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

/* 自动滚动按钮 */
.scroll-to-bottom {
  position: fixed;
  bottom: 100px;
  right: 20px;
  z-index: 100;
}

.scroll-to-bottom .n-button {
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}

/* 会话列表模态框 */
.session-modal {
  width: 400px;
  max-height: 80vh;
}

.session-list-content {
  max-height: 70vh;
  overflow-y: auto;
}

.session-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.session-empty {
  padding: 20px 0;
}

/* 发送记录样式 */
.sent-messages-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
}

.sent-message-item {
  background-color: #f5f5f5;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 10px;
}

.message-text {
  font-size: 14px;
  line-height: 1.6;
  color: #333;
  margin-bottom: 8px;
  white-space: pre-wrap;
}

.message-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #888;
}

.sent-messages-modal {
  width: 500px;
  max-height: 80vh;
}

.sent-messages-content {
  display: flex;
  flex-direction: column;
  max-height: 70vh;
}

.sent-messages-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px 0;
}

.sent-messages-footer {
  margin-top: 16px;
  text-align: right;
}

.sent-messages-empty {
  padding: 40px 0;
}

@media (max-width: 768px) {
  .chat-header {
    padding: 8px 12px;
    flex-direction: column;
    gap: 8px;
  }

  .session-modal {
    width: 90vw;
  }

  .sent-messages-modal {
    width: 90vw;
  }

  .scroll-to-bottom {
    bottom: 90px;
    right: 10px;
  }
}

.pending-images {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 8px;
}

.pending-counter {
  font-size: 12px;
  opacity: 0.75;
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(128, 128, 128, 0.15);
  user-select: none;
}

.pending-image {
  position: relative;
}

.pending-image.error img {
  border-color: #d03050;
  filter: grayscale(0.4);
}

.pending-image img {
  width: 72px;
  height: 72px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid rgba(128, 128, 128, 0.3);
  display: block;
}

.pending-mask {
  position: absolute;
  inset: 0;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.45);
}

.pending-mask.error {
  background: rgba(160, 32, 60, 0.55);
}

.pending-retry {
  border: none;
  border-radius: 12px;
  padding: 3px 12px;
  font-size: 12px;
  color: #fff;
  background: rgba(255, 255, 255, 0.22);
  cursor: pointer;
}

.pending-retry:hover {
  background: rgba(255, 255, 255, 0.35);
}

.pending-spin {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  animation: pending-rotate 0.8s linear infinite;
}

@keyframes pending-rotate {
  to { transform: rotate(360deg); }
}

.drop-overlay {
  position: absolute;
  inset: 0;
  z-index: 5;
  border: 2px dashed rgba(24, 160, 88, 0.85);
  border-radius: 12px;
  background: rgba(24, 160, 88, 0.10);
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  pointer-events: none;
}

.drop-overlay-icon {
  font-size: 28px;
}

.pending-remove {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: none;
  background: rgba(0, 0, 0, 0.65);
  color: #fff;
  font-size: 12px;
  line-height: 18px;
  cursor: pointer;
  padding: 0;
}
</style>
