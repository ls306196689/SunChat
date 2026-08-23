<script setup>
import { ref, onMounted, computed } from 'vue'
import { useMemoryStore } from '@/stores/memory'
import MemoryCard from '@/components/ui/MemoryCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import { NCard, NButton, NInput, NTag, NSpace, useMessage, NScrollbar, NModal } from 'naive-ui'

const memoryStore = useMemoryStore()
const message = useMessage()
const searchQuery = ref('')
const showAddModal = ref(false)
const newMemoryContent = ref('')

onMounted(() => {
  memoryStore.fetchStats()
})

function handleSearch() {
  if (searchQuery.value) {
    memoryStore.searchMemories(searchQuery.value)
  }
}

function handleCreateMemory() {
  showAddModal.value = true
}

async function submitMemory() {
  if (!newMemoryContent.value.trim()) return
  
  try {
    await memoryStore.createMemory(newMemoryContent.value)
    newMemoryContent.value = ''
    showAddModal.value = false
    message.success('记忆创建成功')
    await memoryStore.fetchStats()
  } catch (error) {
    message.error('创建记忆失败: ' + error.message)
  }
}
</script>

<template>
  <div class="memories-view">
    <div class="memories-header">
      <div class="header-left">
        <h2>记忆管理中心</h2>
        <p class="subtitle">AI 自动提取并管理您的个人记忆</p>
      </div>
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
      <EmptyState
        v-if="memoryStore.memories.length === 0 && !memoryStore.loading"
        icon="🧠"
        title="暂无记忆"
        description="开始聊天，AI 将自动提取重要信息并创建记忆"
        action-text="开始聊天"
      />

      <div v-else class="memories-content">
        <MemoryCard
          v-for="memory in memoryStore.memories"
          :key="memory.id"
          :memory="memory"
        />
      </div>
    </div>

    <!-- 添加记忆模态框 -->
    <n-modal
      v-model:show="showAddModal"
      preset="card"
      title="添加记忆"
    >
      <n-input
        v-model:value="newMemoryContent"
        type="textarea"
        placeholder="输入记忆内容（可选类型和分类）"
        :autosize="{ minRows: 4, maxRows: 8 }"
        style="margin-bottom: 16px"
      />
      
      <div class="modal-actions">
        <n-button @click="showAddModal = false">取消</n-button>
        <n-button type="primary" @click="submitMemory">添加</n-button>
      </div>
    </n-modal>
  </div>
</template>

<style scoped>
.memories-view {
  padding: 20px;
  max-width: 900px;
  margin: 0 auto;
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.memories-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-shrink: 0;
}

.header-left h2 {
  margin: 0 0 8px 0;
  font-size: 24px;
  color: #333;
}

.subtitle {
  margin: 0;
  color: #666;
  font-size: 14px;
}

.stats {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
  flex-shrink: 0;
}

.stat-card {
  flex: 1;
  padding: 16px;
}

.stat-item {
  text-align: center;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #18a058;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 12px;
  color: #888;
}

.search-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  flex-shrink: 0;
}

.memories-list {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.memories-content {
  display: flex;
  flex-direction: column;
  gap: 15px;
  overflow-y: auto;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
}

@media (max-width: 768px) {
  .memories-view {
    padding: 12px;
  }

  .memories-header {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }

  .stats {
    flex-direction: column;
  }
}
</style>
