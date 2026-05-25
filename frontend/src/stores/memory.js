import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

const API_BASE_URL = 'http://localhost:8000/api/v1'

export const useMemoryStore = defineStore('memory', () => {
  const memories = ref([])
  const stats = ref(null)
  const loading = ref(false)

  // 获取记忆列表
  async function fetchMemories(type = null, category = null) {
    try {
      loading.value = true
      const params = new URLSearchParams()
      if (type) params.append('type', type)
      if (category) params.append('category', category)

      const response = await axios.get(`${API_BASE_URL}/memories?${params.toString()}`)
      memories.value = response.data.data.memories || []
      return memories.value
    } catch (error) {
      console.error('获取记忆失败:', error)
      return []
    } finally {
      loading.value = false
    }
  }

  // 创建记忆
  async function createMemory(content, type = 'semantic', category = null, tags = []) {
    try {
      const response = await axios.post(`${API_BASE_URL}/memories`, {
        content,
        type,
        category,
        tags
      })
      memories.value.unshift(response.data.data)
      return response.data.data
    } catch (error) {
      console.error('创建记忆失败:', error)
      throw error
    }
  }

  // 搜索记忆
  async function searchMemories(query, top_k = 5) {
    try {
      const response = await axios.post(`${API_BASE_URL}/memories/search`, {
        query,
        top_k
      })
      return response.data.data.results || []
    } catch (error) {
      console.error('搜索记忆失败:', error)
      return []
    }
  }

  // 获取统计
  async function fetchStats() {
    try {
      const response = await axios.get(`${API_BASE_URL}/memories/stats`)
      stats.value = response.data.data
      return stats.value
    } catch (error) {
      console.error('获取统计失败:', error)
      return null
    }
  }

  // 删除记忆
  async function deleteMemory(id) {
    try {
      await axios.delete(`${API_BASE_URL}/memories/${id}`)
      memories.value = memories.value.filter(m => m.id !== id)
      return true
    } catch (error) {
      console.error('删除记忆失败:', error)
      throw error
    }
  }

  return {
    memories,
    stats,
    loading,
    fetchMemories,
    createMemory,
    searchMemories,
    fetchStats,
    deleteMemory
  }
})
