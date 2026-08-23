<script setup>
import { NTag, NSpace } from 'naive-ui'

defineProps({
  memory: {
    type: Object,
    required: true
  }
})
</script>

<template>
  <div class="memory-card">
    <div class="memory-content">
      {{ memory.content }}
    </div>
    <div class="memory-meta">
      <n-space>
        <n-tag
          v-if="memory.type"
          :type="memory.type === 'semantic' ? 'info' : 'success'"
          size="small"
        >
          {{ memory.type }}
        </n-tag>
        <n-tag
          v-if="memory.category"
          type="default"
          size="small"
        >
          {{ memory.category }}
        </n-tag>
        <n-tag
          v-if="memory.confidence"
          type="warning"
          size="small"
        >
          置信度: {{ (memory.confidence * 100).toFixed(0) }}%
        </n-tag>
      </n-space>
      <span class="memory-created">
        {{ memory.created_at ? new Date(memory.created_at).toLocaleDateString() : '刚刚' }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.memory-card {
  padding: 16px;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  transition: transform 0.2s, box-shadow 0.2s;
}

.memory-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 6px rgba(0,0,0,0.15);
}

.memory-content {
  margin-bottom: 12px;
  line-height: 1.6;
  word-wrap: break-word;
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

:deep(.n-tag) {
  padding: 2px 8px;
}
</style>
