<script setup>
import { ref, computed } from 'vue'
import { useThemeStore } from '@/stores/theme'
import Sidebar from '@/components/layout/Sidebar.vue'
import HeaderBar from '@/components/layout/HeaderBar.vue'
import { NConfigProvider, NMessageProvider, NLayout, NLayoutContent } from 'naive-ui'

const themeStore = useThemeStore()

// 主题配置
const themeConfig = computed(() => ({
  common: {
    primaryColor: '#5885f6',
    primaryColorHover: '#6b93f7',
    primaryColorPressed: '#3680e0',
    primaryColorSuppl: '#5885f6',
    infoColor: '#58a7ff',
    successColor: '#18a058',
    warningColor: '#faad14',
    errorColor: '#f24c4c',
    textColorBase: themeStore.isDark ? '#fff' : '#333',
    textColor1: themeStore.isDark ? '#fff' : '#333',
    textColor2: themeStore.isDark ? '#ccc' : '#666',
    textColor3: themeStore.isDark ? '#999' : '#888',
    textColorDisabled: themeStore.isDark ? '#666' : '#ccc',
    backgroundColor: '#f5f5f5',
    backgroundColorOverride: '#f5f5f5',
    bodyColor: '#f5f5f5',
    modalMaskColor: 'rgba(0, 0, 0, 0.5)'
  }
}))

const currentKey = ref('chat')

// 主题切换
function toggleDarkMode() {
  themeStore.toggleTheme()
}
</script>

<template>
  <n-config-provider :theme-overrides="themeConfig" :theme="themeStore.isDark ? 'dark' : null">
    <n-message-provider>
      <n-layout has-sider class="app-layout">
        <Sidebar />
        
        <n-layout class="main-content">
          <HeaderBar />
          
          <n-layout-content class="content-wrapper">
            <router-view />
          </n-layout-content>
          
          <div class="app-footer">
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
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
}

#app {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
}

.app-layout {
  width: 100vw;
  height: 100vh;
}

.app-layout :deep(.n-layout-sider) {
  transition: width 0.3s ease;
}

.main-content {
  background-color: #f5f5f5;
  display: flex;
  flex-direction: column;
  width: 100%;
  min-width: 0;
}

.content-wrapper {
  flex: 1;
  overflow: hidden;
  position: relative;
  min-height: 0;
}

.app-footer {
  background-color: #fff;
  padding: 12px 24px;
  text-align: center;
  color: #666;
  font-size: 12px;
  border-top: 1px solid #eee;
}

.footer-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 1200px;
  margin: 0 auto;
}

/* Dark Mode Styles */
.dark body {
  background-color: #1a1a1a;
  color: #fff;
}

.dark .main-content {
  background-color: #1a1a1a;
}

.dark .app-footer {
  background-color: #252525;
  border-top-color: #333;
  color: #999;
}

.dark .app-footer .footer-content {
  color: #999;
}

/* Scrollbar Styles */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 3px;
}

.dark ::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.3);
}

.dark ::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}
</style>
