<script setup>
import { ref, onMounted } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { NCard, NButton, NSwitch, NSelect, useMessage, NStatistic, NSpace, NInput, NTag, NSpin } from 'naive-ui'
import request from '@/utils/request'

const themeStore = useThemeStore()
const message = useMessage()

// 设置项
const settings = ref({
  theme: 'dark',
  autoSummarize: true,
  memoryRetentionDays: 30,
  searchSource: 'duckduckgo'
})

// API 地址配置
const apiUrl = ref('http://localhost:11434')

// ===== 模型管理状态 =====
const modelLoading = ref(false)
const modelStatus = ref(null) // GET /models 返回的 data
const selectedChatModel = ref('')
const selectedEmbedModel = ref('')
const switchingChat = ref(false)
const switchingEmbed = ref(false)
const rebuilding = ref(false)

// 聊天模型选项
const chatModelOptions = () => {
  const list = modelStatus.value?.chat_models || []
  // 确保当前模型在选项中
  const current = modelStatus.value?.current?.chat_model
  if (current && !list.includes(current)) list.unshift(current)
  return list.map(m => ({ label: m, value: m }))
}

// 嵌入模型选项
const embedModelOptions = () => {
  const list = modelStatus.value?.embedding_models || []
  const current = modelStatus.value?.current?.embedding_model
  if (current && !list.includes(current)) list.unshift(current)
  return list.map(m => ({ label: m, value: m }))
}

// 向量库状态文案
const vectorStoreStatus = () => {
  const vs = modelStatus.value?.vector_store
  if (!vs) return { label: '未知', type: 'default' }
  if (vs.status === 'ok') return { label: '正常', type: 'success' }
  if (vs.status === 'mismatch') return { label: '需重建', type: 'error' }
  return { label: '未记录', type: 'warning' }
}

async function fetchModels() {
  modelLoading.value = true
  try {
    const res = await request.get('/models')
    if (res.code === 200) {
      modelStatus.value = res.data
      // 用 override 或 current 作为下拉选中值
      selectedChatModel.value = res.data.overrides?.chat_model || res.data.current?.chat_model || ''
      selectedEmbedModel.value = res.data.overrides?.embedding_model || res.data.current?.embedding_model || ''
    }
  } catch (e) {
    message.error('获取模型列表失败: ' + (e.message || e))
  } finally {
    modelLoading.value = false
  }
}

async function switchChatModel() {
  if (!selectedChatModel.value) return
  switchingChat.value = true
  try {
    const res = await request.post('/models/chat', { model: selectedChatModel.value })
    if (res.code === 200) {
      message.success('聊天模型已切换为 ' + selectedChatModel.value)
    } else {
      message.error(res.message || '切换失败')
    }
    await fetchModels()
  } catch (e) {
    message.error('切换失败: ' + (e.message || e))
  } finally {
    switchingChat.value = false
  }
}

async function switchEmbedModel() {
  if (!selectedEmbedModel.value) return
  switchingEmbed.value = true
  try {
    const res = await request.post('/models/embedding', { model: selectedEmbedModel.value })
    if (res.code === 200) {
      const needRebuild = res.data?.rebuild_required
      if (needRebuild) {
        message.warning('嵌入模型已切换，向量库维度可能不匹配，建议重建向量库')
      } else {
        message.success('嵌入模型已切换为 ' + selectedEmbedModel.value)
      }
    } else {
      message.error(res.message || '切换失败')
    }
    await fetchModels()
  } catch (e) {
    message.error('切换失败: ' + (e.message || e))
  } finally {
    switchingEmbed.value = false
  }
}

async function rebuildVectors() {
  rebuilding.value = true
  try {
    const res = await request.post('/models/rebuild-vectors')
    if (res.code === 200) {
      const d = res.data
      message.success(`向量库重建完成：共 ${d.total} 条，成功 ${d.rebuilt} 条，失败 ${d.failed} 条`)
    }
    await fetchModels()
  } catch (e) {
    message.error('重建失败: ' + (e.message || e))
  } finally {
    rebuilding.value = false
  }
}

onMounted(() => {
  // 从主题 store 读取当前主题
  settings.value.theme = themeStore.isDark ? 'dark' : 'light'

  // 从 localStorage 读取 API 地址
  const savedSettings = localStorage.getItem('sunchat-settings')
  if (savedSettings) {
    const parsed = JSON.parse(savedSettings)
    if (parsed.apiUrl) {
      apiUrl.value = parsed.apiUrl
    }
  }

  // 加载模型状态
  fetchModels()
})

function handleSave() {
  const config = {
    apiUrl: apiUrl.value,
    ...settings.value
  }
  localStorage.setItem('sunchat-settings', JSON.stringify(config))
  message.success('设置已保存')
}

function handleExport() {
  const data = {
    exportedAt: new Date().toISOString(),
    data: '这里可以导出用户数据'
  }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'sunchat-data.json'
  a.click()
  URL.revokeObjectURL(url)
  message.success('数据已导出')
}

function handleImport() {
  message.info('数据导入功能待实现')
}

function handleClearCache() {
  localStorage.removeItem('sunchat-settings')
  apiUrl.value = 'http://localhost:11434'
  message.success('缓存已清除')
  window.location.reload()
}
</script>

<template>
  <div class="settings-view">
    <n-statistic label="当前主题" :value="themeStore.isDark ? '深色' : '浅色'" style="margin-bottom: 24px; max-width: 300px;">
      <template #prefix>
        <span>{{ themeStore.isDark ? '🌙' : '🌞' }}</span>
      </template>
    </n-statistic>

    <n-card title="界面设置" :bordered="false" class="setting-card">
      <div class="setting-item">
        <div class="setting-info">
          <span class="setting-label">主题</span>
          <span class="setting-desc">切换深色/浅色模式</span>
        </div>
        <n-switch
          v-model:value="settings.theme"
          :checked-text="'深色'"
          :unchecked-text="'浅色'"
          @update:value="(val) => themeStore.setTheme(val ? 'dark' : 'light')"
        />
      </div>
    </n-card>

    <n-card title="记忆设置" :bordered="false" class="setting-card">
      <div class="setting-item">
        <div class="setting-info">
          <span class="setting-label">自动总结对话</span>
          <span class="setting-desc">AI 自动从对话中提取记忆</span>
        </div>
        <n-switch v-model:value="settings.autoSummarize" />
      </div>
      
      <div class="setting-item">
        <div class="setting-info">
          <span class="setting-label">记忆保留天数</span>
          <span class="setting-desc">旧记忆自动清理</span>
        </div>
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
        <div class="setting-info">
          <span class="setting-label">默认搜索源</span>
          <span class="setting-desc">使用 DuckDuckGo 或 SearXNG</span>
        </div>
        <n-select
          v-model:value="settings.searchSource"
          :options="[
            { label: 'DuckDuckGo', value: 'duckduckgo' },
            { label: 'SearXNG', value: 'searxng' }
          ]"
        />
      </div>
    </n-card>

    <n-card :bordered="false" class="setting-card">
      <template #header>
        <div class="model-card-header">
          <span>模型管理</span>
          <n-tag v-if="modelStatus" :type="modelStatus.available ? 'success' : 'error'" size="small" round>
            {{ modelStatus.available ? 'Ollama 在线' : 'Ollama 离线' }}
          </n-tag>
        </div>
      </template>

      <n-spin :show="modelLoading">
        <div v-if="modelStatus" class="model-manage-body">
          <div class="setting-item">
            <div class="setting-info">
              <span class="setting-label">聊天模型</span>
              <span class="setting-desc">用于对话、记忆分析/提取</span>
            </div>
            <div class="model-control">
              <n-select
                v-model:value="selectedChatModel"
                :options="chatModelOptions()"
                size="small"
                style="width: 200px;"
                placeholder="选择聊天模型"
              />
              <n-button size="small" type="primary" :loading="switchingChat" @click="switchChatModel">
                应用
              </n-button>
            </div>
          </div>

          <div class="setting-item">
            <div class="setting-info">
              <span class="setting-label">嵌入模型</span>
              <span class="setting-desc">用于记忆向量检索</span>
            </div>
            <div class="model-control">
              <n-select
                v-model:value="selectedEmbedModel"
                :options="embedModelOptions()"
                size="small"
                style="width: 200px;"
                placeholder="选择嵌入模型"
              />
              <n-button size="small" type="primary" :loading="switchingEmbed" @click="switchEmbedModel">
                应用
              </n-button>
            </div>
          </div>

          <div class="setting-item">
            <div class="setting-info">
              <span class="setting-label">向量库状态</span>
              <span class="setting-desc">
                当前嵌入：{{ modelStatus.current?.embedding_model || '-' }}
                <template v-if="modelStatus.vector_store?.model">
                  ｜向量库：{{ modelStatus.vector_store.model }}
                </template>
              </span>
            </div>
            <div class="model-control">
              <n-tag :type="vectorStoreStatus().type" size="small" round>
                {{ vectorStoreStatus().label }}
              </n-tag>
              <n-button
                size="small"
                type="warning"
                :loading="rebuilding"
                :disabled="vectorStoreStatus().label === '正常'"
                @click="rebuildVectors"
              >
                重建向量库
              </n-button>
            </div>
          </div>
        </div>
        <div v-else class="model-manage-empty">
          暂无模型信息，请确认后端与 Ollama 服务已启动
        </div>
      </n-spin>
    </n-card>

    <n-card title="高级设置" :bordered="false" class="setting-card">
      <div class="setting-item">
        <div class="setting-info">
          <span class="setting-label">API 地址</span>
          <span class="setting-desc">Ollama 服务地址</span>
        </div>
        <n-input
          v-model:value="apiUrl"
          placeholder="http://localhost:11434"
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
.settings-view {
  padding: 20px;
  max-width: 600px;
  margin: 0 auto;
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.settings-view > * {
  margin-bottom: 20px;
}

.settings-view > *:last-child {
  margin-bottom: 0;
  flex: 1;
}

.setting-card {
  flex-shrink: 0;
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

.setting-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.setting-label {
  font-weight: 500;
  color: #333;
}

.setting-desc {
  font-size: 12px;
  color: #888;
}

.model-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.model-manage-body {
  display: flex;
  flex-direction: column;
}

.model-control {
  display: flex;
  align-items: center;
  gap: 8px;
}

.model-manage-empty {
  padding: 20px 0;
  text-align: center;
  color: #999;
  font-size: 13px;
}

@media (max-width: 600px) {
  .model-control {
    flex-direction: column;
    align-items: stretch;
  }
  .model-control .n-select {
    width: 100% !important;
  }
}

.actions {
  margin-top: 20px;
  text-align: center;
}

:deep(.n-statistic-value) {
  font-size: 24px;
  font-weight: bold;
  color: #18a058;
}
</style>
