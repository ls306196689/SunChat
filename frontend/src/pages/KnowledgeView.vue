<script setup>
import { ref, onMounted } from 'vue'
import { useMessage, NButton, NCard, NList, NListItem, NUpload, NSpace, NEmpty } from 'naive-ui'

const message = useMessage()
const files = ref([])

onMounted(() => {
  // 获取文件列表
  fetchFiles()
})

async function fetchFiles() {
  try {
    const response = await fetch('http://localhost:8000/api/v1/kb/files')
    const data = await response.json()
    files.value = data.data.files || []
  } catch (error) {
    console.error('获取文件列表失败:', error)
  }
}

function handleUpload() {
  message.info('文件上传功能待实现')
}
</script>

<template>
  <div class="knowledge-container">
    <div class="header">
      <h2>我的知识库</h2>
      <n-button type="primary" @click="handleUpload">
        + 上传文档
      </n-button>
    </div>

    <n-card v-if="files.length === 0" :bordered="false" class="empty-card">
      <n-empty description="暂无文档">
        <n-button type="primary" @click="handleUpload">上传第一个文档</n-button>
      </n-empty>
    </n-card>

    <n-list v-else bordered class="file-list">
      <n-list-item v-for="file in files" :key="file.id">
        <div class="file-item">
          <div class="file-info">
            <div class="file-name">
              📄 {{ file.original_name }}
              <span v-if="file.status === 'ready'" class="status-ready">✅</span>
              <span v-else class="status-processing">⏳</span>
            </div>
            <div class="file-meta">
              <span>{{ (file.file_size / 1024 / 1024).toFixed(2) }} MB</span>
              <span>{{ file.file_type.toUpperCase() }}</span>
              <span>{{ file.chunk_count }} 个分块</span>
              <span>{{ new Date(file.created_at).toLocaleDateString() }}</span>
            </div>
          </div>
          <div class="file-actions">
            <n-space>
              <n-button size="small" type="info">预览</n-button>
              <n-button size="small" type="warning">重新索引</n-button>
              <n-button size="small" type="error">删除</n-button>
            </n-space>
          </div>
        </div>
      </n-list-item>
    </n-list>
  </div>
</template>

<style scoped>
.knowledge-container {
  padding: 20px;
  max-width: 900px;
  margin: 0 auto;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.empty-card {
  text-align: center;
  padding: 60px 20px;
}

.file-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.file-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.file-info {
  flex: 1;
  margin-right: 20px;
}

.file-name {
  font-weight: bold;
  font-size: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-ready {
  color: #18a058;
}

.status-processing {
  color: #faad14;
}

.file-meta {
  display: flex;
  gap: 15px;
  font-size: 12px;
  color: #888;
  margin-top: 4px;
}

.file-actions {
  display: flex;
  gap: 8px;
}
</style>
