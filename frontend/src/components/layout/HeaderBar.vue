<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const pageTitle = computed(() => {
  const map = {
    '/': '聊天',
    '/memories': '记忆管理',
    '/knowledge': '知识库',
    '/settings': '系统设置'
  }
  return map[route.path] || '聊天'
})

defineProps({
  showBack: {
    type: Boolean,
    default: false
  }
})

defineEmits(['back'])
</script>

<template>
  <div class="app-header">
    <div class="header-left" v-if="showBack">
      <n-button
        text
        @click="$emit('back')"
        class="back-btn"
      >
        ← 返回
      </n-button>
    </div>
    
    <div class="header-title">
      {{ pageTitle }}
    </div>
    
    <div class="header-right">
      <!-- 可添加用户信息、通知等 -->
    </div>
  </div>
</template>

<style scoped>
.app-header {
  height: 64px;
  background-color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  border-bottom: 1px solid #eee;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
}

.back-btn {
  color: #5885f6;
  font-weight: 500;
}

.back-btn:hover {
  color: #3680e0;
}

.header-title {
  font-size: 18px;
  font-weight: bold;
  color: #333;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

@media (max-width: 768px) {
  .app-header {
    padding: 0 16px;
  }
  
  .header-title {
    font-size: 16px;
  }
}
</style>
