import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import request from '@/utils/request'

export const useChatStore = defineStore('chat', () => {
  const sessions = ref([])
  const currentSession = ref(null)
  const messages = ref([])
  const loading = ref(false)
  const error = ref(null)
  const autoLoadMore = ref(true)

  // 获取会话列表
  async function fetchSessions() {
    try {
      const response = await request.get('/chat/sessions')
      // 兼容不同的响应格式
      sessions.value = response.data || response || []
      return sessions.value
    } catch (err) {
      error.value = err.message || '获取会话列表失败'
      console.error('获取会话列表失败:', err)
      return []
    }
  }

  // 创建新会话
  async function createSession() {
    try {
      const response = await request.post('/chat/sessions')
      currentSession.value = response.data
      messages.value = []
      error.value = null
      return response.data
    } catch (err) {
      error.value = err.message || '创建会话失败'
      console.error('创建会话失败:', err)
      return null
    }
  }

  // 切换会话
  async function switchSession(sessionId) {
    loading.value = true
    try {
      const response = await request.get(`/chat/sessions/${sessionId}/messages`)
      currentSession.value = sessions.value.find(s => s.session_id === sessionId) || { session_id: sessionId }
      messages.value = response.data.messages || []
      error.value = null
      return messages.value
    } catch (err) {
      error.value = err.message || '获取消息失败'
      console.error('获取消息失败:', err)
      return []
    } finally {
      loading.value = false
    }
  }

  // 获取消息历史
  async function fetchMessages(sessionId) {
    try {
      loading.value = true
      const response = await request.get(`/chat/sessions/${sessionId}/messages`)
      messages.value = response.data.messages || []
      error.value = null
      return messages.value
    } catch (err) {
      error.value = err.message || '获取消息失败'
      console.error('获取消息失败:', err)
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

    // 用于在错误回滚时定位本次发送的消息
    const timestamp = Date.now()
    try {
      loading.value = true
      error.value = null

      // 乐观更新 - 添加用户消息和占位的 AI 消息
      const userMsg = {
        id: timestamp,
        role: 'user',
        content,
        created_at: new Date().toISOString()
      }
      console.log('[ChatStore] 发送用户消息:', userMsg)
      messages.value.push(userMsg)

      // 占位 AI 消息（空内容，loading 为 true）
      const placeholderId = timestamp + 1
      const placeholderMsg = {
        id: placeholderId,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString()
      }
      messages.value.push(placeholderMsg)

      const response = await request.post('/chat/messages', {
        session_id: currentSession.value.session_id,
        content,
        memory_context: memoryContext,
        search_enabled: searchEnabled
      })

      console.log('[ChatStore] 收到响应:', response)
      console.log('[ChatStore] 响应类型:', typeof response)
      console.log('[ChatStore] 响应 keys:', Object.keys(response || {}))

      // 从响应中提取 AI 消息内容
      const aiContent = response?.response || response?.data?.response || response?.data?.data?.response || ''
      console.log('[ChatStore] AI 响应内容:', aiContent)

      // 替换占位消息的内容
      const idx = messages.value.findIndex(m => m.id === placeholderId)
      if (idx !== -1) {
        messages.value[idx].content = aiContent
        messages.value[idx].created_at = new Date().toISOString()
      } else {
        // 若未找到占位，则直接添加
        messages.value.push({
          id: placeholderId,
          role: 'assistant',
          content: aiContent,
          created_at: new Date().toISOString()
        })
      }

      error.value = null
      return response
    } catch (err) {
      // 移除乐观更新的消息（用户消息和占位 AI 消息）
      // 移除本次发送的用户消息和占位 AI 消息
      messages.value = messages.value.filter(msg => msg.id < timestamp)
      error.value = err.message || '发送消息失败'
      console.error('发送消息失败:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  // 清空消息
  function clearMessages() {
    messages.value = []
    error.value = null
  }

  // 清空会话
  function clearSessions() {
    sessions.value = []
    currentSession.value = null
    messages.value = []
  }

  return {
    sessions,
    currentSession,
    messages,
    loading,
    error,
    autoLoadMore,
    
    // actions
    fetchSessions,
    createSession,
    switchSession,
    fetchMessages,
    sendMessage,
    clearMessages,
    clearSessions
  }
})
