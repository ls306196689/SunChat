<script setup>
import { computed } from 'vue'

defineProps({
  session: {
    type: Object,
    required: true
  },
  active: {
    type: Boolean,
    default: false
  }
})

defineEmits(['click'])
</script>

<template>
  <div
    class="session-item"
    :class="{ active }"
    @click="$emit('click')"
  >
    <div class="session-title">
      {{ session.title }}
    </div>
    <div class="session-meta">
      <span>{{ session.message_count || 0 }} 条消息</span>
      <span>{{ session.updated_at ? new Date(session.updated_at).toLocaleDateString() : '' }}</span>
    </div>
  </div>
</template>

<style scoped>
.session-item {
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s;
  background-color: transparent;
}

.session-item:hover {
  background-color: rgba(0,0,0,0.05);
}

.session-item.active {
  background-color: #5885f6;
  color: white;
}

.session-item.active .session-meta {
  color: rgba(255,255,255,0.7);
}

.session-title {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 4px;
  line-height: 1.4;
}

.session-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #888;
}
</style>
