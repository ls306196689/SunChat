<script setup>
import { ref, onMounted } from 'vue'
import { useMemoryStore } from '../stores/memory'
import { NCard, NButton, NInput, NTag, NSpace, useMessage, NEmpty } from 'naive-ui'

const memoryStore = useMemoryStore()
const message = useMessage()
const searchQuery = ref('')

onMounted(() => {
  memoryStore.fetchStats()
})

function handleSearch() {
  if (searchQuery.value) {
    memoryStore.searchMemories(searchQuery.value)
  }
}

function handleCreateMemory() {
  message.info('创建记忆功能待实现')
}
</script>

<template>
  <div class="memories-container">
    <div class="header">
      <h2>记忆管理中心</h2>
      <n-button type="primary" @click="handleCreateMemory">
        + 手动添加记忆
      </n-button>
    </div>

    <div class="stats">
      <n-card v-if="memoryStore.stats" :bordered="false" class="stat-card">
        <div class="stat-item">
          <div class="stat-value">{{ memoryStore.stats.total_count || 0 }}</div>
          <div class="stat-label">总记忆数</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ memoryStore.stats.by_type?.semantic || 0 }}</div>
          <div class="stat-label">语义记忆</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ memoryStore.stats.by_type?.episodic || 0 }}</div>
          <div class="stat-label">情景记忆</div>
        </div>
      </n-card>
    </div>

    <div class="search-bar">
      <n-input
        v-model:value="searchQuery"
        placeholder="搜索记忆..."
        @keydown.enter="handleSearch"
      />
      <n-button type="primary" @click="handleSearch">搜索</n-button>
    </div>

    <div class="memories-list">
      <n-empty v-if="memoryStore.memories.length === 0" description="暂无记忆">
        <n-button type="primary" @click="handleCreateMemory">添加记忆</n-button>
      </n-empty>

      <n-card
        v-for="memory in memoryStore.memories"
        :key="memory.id"
        class="memory-card"
        :bordered="false"
      >
        <div class="memory-content">{{ memory.content }}</div>
        <div class="memory-meta">
          <n-space>
            <n-tag v-if="memory.type" :type="memory.type === 'semantic' ? 'info' : 'success'">
              {{ memory.type }}
            </n-tag>
            <n-tag v-if="memory.category" type="default">
              {{ memory.category }}
            </n-tag>
            <n-tag v-if="memory.confidence" type="warning">
              置信度: {{ (memory.confidence * 100).toFixed(0) }}%
            </n-tag>
          </n-space>
          <span class="memory-created">
            {{ memory.created_at ? new Date(memory.created_at).toLocaleDateString() : '刚刚' }}
          </span>
        </div>
      </n-card>
    </div>
  </div>
</template>

<style scoped>
.memories-container {
  padding: 20px;
  max-width: 900px;
  margin: 0 auto;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.stats {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
}

.stat-card {
  flex: 1;
}

.stat-item {
  text-align: center;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #18a058;
}

.stat-label {
  font-size: 12px;
  color: #888;
  margin-top: 4px;
}

.search-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.memories-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.memory-card {
  transition: transform 0.2s;
}

.memory-content {
  margin-bottom: 12px;
  line-height: 1.6;
}

.memory-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #888;
}

.memory-created {
  font-size: 12px;
  color: #999;
}
</style>
