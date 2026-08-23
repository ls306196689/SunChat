import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/utils/request'

export const useMemoryStore = defineStore('memory', () => {
  const memories = ref([])
  const stats = ref(null)
  const loading = ref(false)
  const error = ref(null)

  // 获取记忆列表
  async function fetchMemories(type = null, category = null) {
    try {
      loading.value = true
      error.value = null
      
      const params = new URLSearchParams()
      if (type) params.append('type', type)
      if (category) params.append('category', category)

      const response = await request.get(`/memories?${params.toString()}`)
      memories.value = response.data.memories || response.data || []
      return memories.value
    } catch (err) {
      error.value = err.message || '获取记忆失败'
      console.error('获取记忆失败:', err)
      return []
    } finally {
      loading.value = false
    }
  }

  // 创建记忆
  async function createMemory(content, type = 'semantic', category = null, tags = []) {
    try {
      const response = await request.post('/memories', {
        content,
        type,
        category,
        tags
      })
      memories.value.unshift(response.data)
      error.value = null
      return response.data
    } catch (err) {
      error.value = err.message || '创建记忆失败'
      console.error('创建记忆失败:', err)
      throw err
    }
  }

  // 搜索记忆
  async function searchMemories(query, top_k = 5) {
    try {
      loading.value = true
      error.value = null
      
      const response = await request.post('/memories/search', {
        query,
        top_k
      })
      
      memories.value = response.data.results || response.data || []
      return memories.value
    } catch (err) {
      error.value = err.message || '搜索记忆失败'
      console.error('搜索记忆失败:', err)
      return []
    } finally {
      loading.value = false
    }
  }

  // 获取统计
  async function fetchStats() {
    try {
      loading.value = true
      error.value = null
      
      const response = await request.get('/memories/stats')
      stats.value = response.data || response || null
      return stats.value
    } catch (err) {
      error.value = err.message || '获取统计失败'
      console.error('获取统计失败:', err)
      return null
    } finally {
      loading.value = false
    }
  }

  // 删除记忆
  async function deleteMemory(id) {
    try {
      await request.delete(`/memories/${id}`)
      memories.value = memories.value.filter(m => m.id !== id)
      error.value = null
      return true
    } catch (err) {
      error.value = err.message || '删除记忆失败'
      console.error('删除记忆失败:', err)
      throw err
    }
  }

  // 清空状态
  function clearMemories() {
    memories.value = []
    stats.value = null
    error.value = null
  }

  return {
    memories,
    stats,
    loading,
    error,
    
    // actions
    fetchMemories,
    createMemory,
    searchMemories,
    fetchStats,
    deleteMemory,
    clearMemories
  }
})
