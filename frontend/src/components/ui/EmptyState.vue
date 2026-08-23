<script setup>
defineProps({
  icon: {
    type: String,
    default: ''
  },
  title: {
    type: String,
    default: ''
  },
  description: {
    type: String,
    default: ''
  },
  actionText: {
    type: String,
    default: ''
  }
})

defineEmits(['action'])
</script>

<template>
  <div class="empty-state">
    <div class="empty-icon" v-if="icon">
      {{ icon }}
    </div>
    <div class="empty-title" v-if="title">
      {{ title }}
    </div>
    <div class="empty-description" v-if="description">
      {{ description }}
    </div>
    <n-button
      v-if="actionText"
      type="primary"
      @click="$emit('action')"
    >
      {{ actionText }}
    </n-button>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
  color: #888;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-title {
  font-size: 18px;
  font-weight: bold;
  margin-bottom: 8px;
  color: #333;
}

.empty-description {
  font-size: 14px;
  margin-bottom: 24px;
  line-height: 1.5;
}

.empty-state :deep(.n-button) {
  margin-top: 16px;
}
</style>
