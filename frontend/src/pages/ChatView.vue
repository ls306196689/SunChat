<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useChatStore } from '../stores/chat'
import { useMemoryStore } from '../stores/memory'
import { NInput, NButton, NSpace, NList, NListItem, NCard,useMessage, NScrollbar } from 'naive-ui'
import { marked } from 'marked'

const chatStore = useChatStore()
const memoryStore = useMemoryStore()
const message = useMessage()

const inputContent = ref('')
const memoryEnabled = ref(true)
const searchEnabled = ref(true)

onMounted(() => {
  chatStore.fetchSessions()
  memoryStore.fetchStats()
})

async function handleSend() {
  if (!inputContent.value.trim()) return

  try {
    await chatStore.sendMessage(
      inputContent.value,
      memoryEnabled.value,
      searchEnabled.value
    )
    inputContent.value = ''
  } catch (error) {
    message.error('发送消息失败: ' + (error.message || '未知错误'))
  }
}

function handleKeyDown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSend()
  }
}

// 渲染 Markdown
function renderMarkdown(text) {
  return marked(text)
}

// 时间格式化
function formatTime(time) {
  return new Date(time).toLocaleString('zh-CN')
}
</script>

<template>
  <n-card class="chat-container">
    <n-list class="message-list">
      <n-list-item v-for="msg in chatStore.messages" :key="msg.id">
        <div :class="['message-item', msg.role]">
          <div class="avatar">
            {{ msg.role === 'user' ? '👤' : '🤖' }}
          </div>
          <div class="content">
            <div class="meta">
              <span>{{ msg.role === 'user' ? '你' : 'AI 助手' }}</span>
              <span>{{ formatTime(msg.created_at) }}</span>
            </div>
            <div v-html="renderMarkdown(msg.content)" class="text"></div>
          </div>
        </div>
      </n-list-item>
    </n-list>

    <div class="input-area">
      <div class="settings">
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
      </div>

      <n-input
        v-model:value="inputContent"
        type="textarea"
        placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
        :autosize="{ minRows: 2, maxRows: 6 }"
        @keydown="handleKeyDown"
      />

      <div class="actions">
        <n-button type="primary" @click="handleSend">发送</n-button>
      </div>
    </div>
  </n-card>
</template>

<style scoped>
.chat-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  padding: 0;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.message-item {
  display: flex;
  margin-bottom: 20px;
}

.message-item.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background-color: #18a058;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 10px;
}

.message-item.user .avatar {
  background-color: #5885f6;
}

.content {
  max-width: 70%;
}

.meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #888;
  margin-bottom: 8px;
}

.text {
  background-color: #f5f5f5;
  padding: 12px 16px;
  border-radius: 8px;
  line-height: 1.6;
  word-wrap: break-word;
}

.message-item.user .content {
  background-color: #e8f5e9;
}

.input-area {
  padding: 20px;
  background-color: #fff;
  border-top: 1px solid #eee;
}

.settings {
  margin-bottom: 10px;
}

.actions {
  margin-top: 10px;
  text-align: right;
}
</style>
