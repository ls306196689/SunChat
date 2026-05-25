import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

const API_BASE_URL = 'http://localhost:8000/api/v1'

export const useChatStore = defineStore('chat', () => {
  const sessions = ref([])
  const currentSession = ref(null)
  const messages = ref([])
  const loading = ref(false)

  // 获取会话列表
  async function fetchSessions() {
    try {
      const response = await axios.get(`${API_BASE_URL}/chat/sessions`)
      // 兼容不同的响应格式
      sessions.value = response.data.data || response.data || []
      return sessions.value
    } catch (error) {
      console.error('获取会话列表失败:', error)
      return []
    }
  }

  // 创建新会话
  async function createSession() {
    try {
      const response = await axios.post(`${API_BASE_URL}/chat/sessions`)
      currentSession.value = response.data.data
      messages.value = []
      return response.data.data
    } catch (error) {
      console.error('创建会话失败:', error)
      return null
    }
  }

  // 获取消息历史
  async function fetchMessages(sessionId) {
    try {
      loading.value = true
      const response = await axios.get(
        `${API_BASE_URL}/chat/sessions/${sessionId}/messages`
      )
      messages.value = response.data.data.messages || []
      return messages.value
    } catch (error) {
      console.error('获取消息失败:', error)
      return []
    } finally {
      loading.value = false
    }
  }

  // 发送消息
  async function sendMessage(content, memoryContext = true, searchEnabled = true) {
    if (!currentSession.value) {
      await createSession()
    }

    try {
      loading.value = true
      const response = await axios.post(`${API_BASE_URL}/chat/messages`, {
        session_id: currentSession.value.session_id,
        content,
        memory_context: memoryContext,
        search_enabled: searchEnabled
      })

      // 添加用户消息
      messages.value.push({
        id: Date.now(),
        role: 'user',
        content,
        created_at: new Date().toISOString()
      })

      // 添加 AI 消息
      messages.value.push({
        id: Date.now() + 1,
        role: 'assistant',
        content: response.data.response,
        created_at: new Date().toISOString()
      })

      return response.data
    } catch (error) {
      console.error('发送消息失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  // 清空消息
  function clearMessages() {
    messages.value = []
  }

  return {
    sessions,
    currentSession,
    messages,
    loading,
    fetchSessions,
    createSession,
    fetchMessages,
    sendMessage,
    clearMessages
  }
})
