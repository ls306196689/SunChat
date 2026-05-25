<script setup>
import { ref } from 'vue'
import { NCard, NButton, NSwitch, NSelect, useMessage } from 'naive-ui'

const message = useMessage()

// 设置项
const settings = ref({
  theme: 'dark',
  autoSummarize: true,
  memoryRetentionDays: 30,
  searchSource: 'duckduckgo'
})

function handleSave() {
  message.success('设置已保存')
}

function handleExport() {
  message.info('数据导出功能待实现')
}

function handleImport() {
  message.info('数据导入功能待实现')
}
</script>

<template>
  <div class="settings-container">
    <h2>系统设置</h2>

    <n-card title="界面设置" :bordered="false" class="setting-card">
      <div class="setting-item">
        <span>主题</span>
        <n-select
          v-model:value="settings.theme"
          :options="[
            { label: '深色', value: 'dark' },
            { label: '浅色', value: 'light' }
          ]"
        />
      </div>
    </n-card>

    <n-card title="记忆设置" :bordered="false" class="setting-card">
      <div class="setting-item">
        <span>自动总结对话</span>
        <n-switch v-model:value="settings.autoSummarize" />
      </div>
      <div class="setting-item">
        <span>记忆保留天数</span>
        <n-select
          v-model:value="settings.memoryRetentionDays"
          :options="[
            { label: '7天', value: 7 },
            { label: '30天', value: 30 },
            { label: '90天', value: 90 },
            { label: '永久', value: -1 }
          ]"
        />
      </div>
    </n-card>

    <n-card title="搜索设置" :bordered="false" class="setting-card">
      <div class="setting-item">
        <span>默认搜索源</span>
        <n-select
          v-model:value="settings.searchSource"
          :options="[
            { label: 'DuckDuckGo', value: 'duckduckgo' },
            { label: 'SearXNG', value: 'searxng' }
          ]"
        />
      </div>
    </n-card>

    <n-card title="数据管理" :bordered="false" class="setting-card">
      <n-space>
        <n-button type="info" @click="handleExport">导出数据</n-button>
        <n-button type="info" @click="handleImport">导入数据</n-button>
        <n-button type="error" @click="handleClearCache">清除缓存</n-button>
      </n-space>
    </n-card>

    <div class="actions">
      <n-button type="primary" @click="handleSave">保存设置</n-button>
    </div>
  </div>
</template>

<style scoped>
.settings-container {
  padding: 20px;
  max-width: 600px;
  margin: 0 auto;
}

.settings-container h2 {
  margin-bottom: 20px;
}

.setting-card {
  margin-bottom: 20px;
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0;
  border-bottom: 1px solid #eee;
}

.setting-item:last-child {
  border-bottom: none;
}

.actions {
  margin-top: 20px;
  text-align: right;
}
</style>
