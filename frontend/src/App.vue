<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

// 侧边栏菜单
const menuItems = [
  {
    label: '聊天',
    key: 'chat'
  },
  {
    label: '记忆',
    key: 'memories'
  },
  {
    label: '知识库',
    key: 'knowledge'
  },
  {
    label: '设置',
    key: 'settings'
  }
]

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
</script>

<template>
  <n-config-provider>
    <n-message-provider>
      <n-layout has-sider class="layout">
        <n-layout-sider
          bordered
          collapse-mode="width"
          :collapsed-width="64"
          :width="240"
          :default-collapsed="false"
          class="sidebar"
        >
          <div class="logo">
            SunChat
          </div>
          <n-menu
            :options="menuItems"
            :selected-keys="[currentKey]"
            @update:selected-keys="handleSelect"
          />
        </n-layout-sider>

        <n-layout class="main-content">
          <div class="header">
            <span class="page-title">
              {{ currentKey === 'chat' ? '聊天' : currentKey === 'memories' ? '记忆管理' : currentKey === 'knowledge' ? '知识库' : '设置' }}
            </span>
          </div>

          <n-layout-content>
            <router-view />
          </n-layout-content>

          <div class="footer">
            <div class="footer-content">
              <span>SunChat v1.0.0 - 你的个人 AI 助手</span>
              <span>本地运行中</span>
            </div>
          </div>
        </n-layout>
      </n-layout>
    </n-message-provider>
  </n-config-provider>
</template>

<style>
.layout {
  height: 100vh;
  width: 100vw;
}

.sidebar {
  background-color: #1a1a1a;
  color: #fff;
}

.logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: bold;
  border-bottom: 1px solid #333;
}

.main-content {
  background-color: #f5f5f5;
  display: flex;
  flex-direction: column;
}

.header {
  background-color: #fff;
  display: flex;
  align-items: center;
  padding: 0 24px;
  height: 64px;
  border-bottom: 1px solid #eee;
}

.page-title {
  font-size: 18px;
  font-weight: bold;
  color: #333;
}

.footer {
  background-color: #fff;
  padding: 16px 24px;
  text-align: center;
  color: #666;
  font-size: 14px;
  border-top: 1px solid #eee;
  margin-top: auto;
}

.footer-content {
  display: flex;
  justify-content: space-between;
}
</style>
