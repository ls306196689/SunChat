<script setup>
const props = defineProps({
  session: {
    type: Object,
    required: true
  },
  active: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['click', 'rename', 'remove'])

function onRename() {
  const title = window.prompt('会话名称', props.session.title)
  if (title && title.trim() && title.trim() !== props.session.title) {
    emit('rename', title.trim())
  }
}
</script>

<template>
  <div
    class="session-item"
    :class="{ active }"
    @click="$emit('click')"
  >
    <div class="session-row">
      <div class="session-title">
        {{ session.title }}
      </div>
      <div class="session-actions" @click.stop>
        <button class="action-btn" title="重命名" @click="onRename">改名</button>
        <button class="action-btn danger" title="删除" @click="$emit('remove')">删除</button>
      </div>
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

.session-item.active .action-btn {
  color: rgba(255,255,255,0.85);
  border-color: rgba(255,255,255,0.4);
}

.session-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.session-title {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 4px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.session-actions {
  display: none;
  gap: 4px;
}

.session-item:hover .session-actions {
  display: flex;
}

.action-btn {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid rgba(0,0,0,0.15);
  background: transparent;
  cursor: pointer;
  color: inherit;
}

.action-btn:hover {
  background: rgba(0,0,0,0.08);
}

.action-btn.danger:hover {
  background: #d03050;
  color: white;
  border-color: #d03050;
}

.session-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #888;
}
</style>
