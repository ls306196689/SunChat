import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import request from '@/utils/request'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

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

  // SSE 流式调用：meta/delta/done/error 帧。返回是否收到过任何帧。
  async function streamChat(payload, { onMeta, onDelta }) {
    const response = await fetch(`${API_BASE_URL}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    if (!response.ok || !response.body) {
      const err = new Error(`HTTP ${response.status}`)
      err.status = response.status
      err.received = false
      throw err
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let received = false
    let streamError = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      received = true
      buffer += decoder.decode(value, { stream: true })
      // SSE 帧以空行分隔
      let sep
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)
        for (const line of frame.split('\n')) {
          if (!line.startsWith('data: ')) continue
          let data
          try { data = JSON.parse(line.slice(6)) } catch { continue }
          if (data.type === 'meta') onMeta && onMeta(data)
          else if (data.type === 'delta') onDelta && onDelta(data.content || '')
          else if (data.type === 'error') streamError = new Error(data.error || '生成失败')
        }
      }
    }
    if (streamError) {
      streamError.received = received
      throw streamError
    }
    return received
  }

  // 发送消息（默认 SSE 流式；网络级失败自动回退非流式接口）
  async function sendMessage(content, memoryContext = true, searchEnabled = true, imageIds = []) {
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
        images: Array.isArray(imageIds) ? [...imageIds] : [],
        created_at: new Date().toISOString()
      }
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

      const payload = {
        session_id: currentSession.value.session_id,
        content,
        memory_context: memoryContext,
        search_enabled: searchEnabled,
        images: Array.isArray(imageIds) ? imageIds : []
      }

      const patchPlaceholder = (fn) => {
        const idx = messages.value.findIndex(m => m.id === placeholderId)
        if (idx !== -1) fn(messages.value[idx])
        return idx !== -1
      }

      try {
        await streamChat(payload, {
          onMeta: (meta) => {
            patchPlaceholder(m => {
              if (meta.memory_context) m.memory_context = meta.memory_context
              if (meta.sources) m.sources = meta.sources
            })
          },
          onDelta: (piece) => {
            patchPlaceholder(m => {
              m.content += piece
              m.created_at = new Date().toISOString()
            })
          }
        })
        error.value = null
        return
      } catch (streamErr) {
        // 首帧都没收到 → 视为环境不支持流式，回退非流式接口
        if (!streamErr.received) {
          console.warn('[ChatStore] SSE 不可用，回退非流式:', streamErr)
          try {
            const response = await request.post('/chat/messages', payload)
            const aiContent = response?.data?.response ?? response?.response ?? ''
            patchPlaceholder(m => {
              m.content = aiContent
              if (response?.data?.sources) m.sources = response.data.sources
              m.created_at = new Date().toISOString()
            })
            error.value = null
            return response
          } catch (fallbackErr) {
            // 回退也失败：消息未入库，回滚乐观更新
            messages.value = messages.value.filter(msg => msg.id < timestamp)
            throw fallbackErr
          }
        }
        // 流中断：用户消息已入库，保留消息并在占位处显示错误
        patchPlaceholder(m => {
          m.content = m.content || `⚠️ ${streamErr.message}`
        })
        throw streamErr
      }
    } catch (err) {
      error.value = err.message || '发送消息失败'
      console.error('发送消息失败:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  // 重命名会话
  async function renameSession(sessionId, title) {
    try {
      await request.patch(`/chat/sessions/${sessionId}`, null, { params: { title } })
      const s = sessions.value.find(x => x.session_id === String(sessionId))
      if (s) s.title = title
      return true
    } catch (err) {
      error.value = err.message || '重命名失败'
      console.error('重命名会话失败:', err)
      return false
    }
  }

  // 删除会话
  async function removeSession(sessionId) {
    try {
      await request.delete(`/chat/sessions/${sessionId}`)
      sessions.value = sessions.value.filter(s => s.session_id !== String(sessionId))
      if (currentSession.value && currentSession.value.session_id === String(sessionId)) {
        currentSession.value = sessions.value[0] || null
        messages.value = []
      }
      return true
    } catch (err) {
      error.value = err.message || '删除失败'
      console.error('删除会话失败:', err)
      return false
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
    streamChat,
    renameSession,
    removeSession,
    clearMessages,
    clearSessions
  }
})
