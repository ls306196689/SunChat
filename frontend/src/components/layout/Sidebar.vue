<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NLayoutSider, NLayout, NMenu, useMessage } from 'naive-ui'

const route = useRoute()
const router = useRouter()
const message = useMessage()

// 侧边栏菜单
const menuItems = ref([
  {
    label: '聊天',
    key: 'chat',
    icon: () => '💬'
  },
  {
    label: '记忆',
    key: 'memories',
    icon: () => '🧠'
  },
  {
    label: '知识库',
    key: 'knowledge',
    icon: () => '📚'
  },
  {
    label: '设置',
    key: 'settings',
    icon: () => '⚙️'
  }
])

const collapsed = ref(false)
const currentKey = computed(() => {
  const map = {
    '/': 'chat',
    '/memories': 'memories',
    '/knowledge': 'knowledge',
    '/settings': 'settings'
  }
  return map[route.path] || 'chat'
})

function handleSelect(key) {
  const map = {
    'chat': '/',
    'memories': '/memories',
    'knowledge': '/knowledge',
    'settings': '/settings'
  }
  router.push(map[key])
}

function handleToggleCollapse() {
  collapsed.value = !collapsed.value
}

// 移动端检测
const isMobile = ref(false)

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

function checkMobile() {
  isMobile.value = window.innerWidth < 768
  if (isMobile.value) {
    collapsed.value = true
  }
}

function getSidebarWidth() {
  if (isMobile.value) return 0
  return collapsed.value ? 64 : 240
}

defineExpose({
  collapsed,
  toggleCollapse: handleToggleCollapse
})
</script>

<template>
  <n-layout-sider
    bordered
    collapse-mode="width"
    :collapsed-width="64"
    :width="getSidebarWidth()"
    :default-collapsed="collapsed"
    class="app-sidebar"
    :class="{ 'mobile-collapsed': isMobile }"
  >
    <div class="logo" @click="handleToggleCollapse" v-if="!isMobile">
      <span class="logo-icon">💬</span>
      <span class="logo-text">SunChat</span>
    </div>
    
    <div class="logo mobile-logo" v-else @click="handleToggleCollapse">
      <span class="logo-icon">💬</span>
    </div>

    <n-menu
      :options="menuItems"
      :selected-keys="[currentKey]"
      @select="handleSelect"
      style="margin-top: 20px"
    />

    <div class="sidebar-footer">
      <n-button
        text
        @click="handleToggleCollapse"
        class="collapse-btn"
      >
        {{ collapsed ? '展开' : '收起' }}
      </n-button>
      <div class="version-info">
        v1.0.0
      </div>
    </div>
  </n-layout-sider>
</template>

<style scoped>
.app-sidebar {
  background-color: #1a1a1a;
  color: #fff;
  transition: width 0.3s ease;
}

.logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: bold;
  border-bottom: 1px solid #333;
  cursor: pointer;
  transition: all 0.2s;
}

.logo:hover {
  background-color: rgba(255,255,255,0.1);
}

.logo-icon {
  margin-right: 8px;
  font-size: 24px;
}

.logo-text {
  color: #fff;
}

.mobile-logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.mobile-logo .logo-icon {
  font-size: 28px;
}

:deep(.n-menu) {
  color: #fff;
}

:deep(.n-menu-item) {
  color: rgba(255,255,255,0.7);
}

:deep(.n-menu-item--selected) {
  background-color: #5885f6;
  color: #fff;
}

.sidebar-footer {
  position: absolute;
  bottom: 0;
  width: 100%;
  padding: 16px;
  border-top: 1px solid #333;
  background-color: #1a1a1a;
}

.collapse-btn {
  width: 100%;
  justify-content: center;
  color: rgba(255,255,255,0.7);
}

.version-info {
  margin-top: 8px;
  font-size: 12px;
  color: rgba(255,255,255,0.5);
  text-align: center;
}

@media (max-width: 768px) {
  .app-sidebar {
    position: fixed;
    z-index: 1000;
    transition: transform 0.3s ease;
  }

  :deep(.n-menu) {
    margin-top: 0;
  }
}
</style>
