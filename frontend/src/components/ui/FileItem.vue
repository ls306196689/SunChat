<script setup>
import { NButton, NSpace } from 'naive-ui'

defineProps({
  file: {
    type: Object,
    required: true
  }
})

defineEmits(['preview', 'reindex', 'delete'])
</script>

<template>
  <div class="file-item">
    <div class="file-info">
      <div class="file-name">
        📄 {{ file.original_name }}
        <span v-if="file.status === 'ready'" class="status-ready">✅</span>
        <span v-else class="status-processing">⏳</span>
      </div>
      <div class="file-meta">
        <span>{{ (file.file_size / 1024 / 1024).toFixed(2) }} MB</span>
        <span>{{ file.file_type.toUpperCase() }}</span>
        <span>{{ file.chunk_count }} 个分块</span>
        <span>{{ new Date(file.created_at).toLocaleDateString() }}</span>
      </div>
    </div>
    <div class="file-actions">
      <n-space>
        <n-button size="small" type="info" @click="$emit('preview')">
          预览
        </n-button>
        <n-button size="small" type="warning" @click="$emit('reindex')">
          重新索引
        </n-button>
        <n-button size="small" type="error" @click="$emit('delete')">
          删除
        </n-button>
      </n-space>
    </div>
  </div>
</template>

<style scoped>
.file-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  transition: transform 0.2s, box-shadow 0.2s;
}

.file-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 6px rgba(0,0,0,0.15);
}

.file-info {
  flex: 1;
  margin-right: 20px;
}

.file-name {
  font-weight: bold;
  font-size: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-ready {
  color: #18a058;
}

.status-processing {
  color: #faad14;
}

.file-meta {
  display: flex;
  gap: 15px;
  font-size: 12px;
  color: #888;
  margin-top: 4px;
}

.file-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
</style>
