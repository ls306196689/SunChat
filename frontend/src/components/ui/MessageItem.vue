<script setup>
import { computed } from 'vue'
import { chatImageUrl } from '@/utils/request'

const props = defineProps({
  role: {
    type: String,
    required: true,
    validator: (value) => ['user', 'assistant'].includes(value)
  },
  content: {
    type: String,
    default: ''
  },
  createTime: {
    type: String,
    default: ''
  },
  loading: {
    type: Boolean,
    default: false
  },
  sources: {
    type: Array,
    default: () => []
  },
  images: {
    type: Array,
    default: () => []
  }
})

const userClass = computed(() => `message-item ${props.role}`)
const avatar = computed(() => props.role === 'user' ? '👤' : '🤖')
const name = computed(() => props.role === 'user' ? '你' : 'AI 助手')
</script>

<template>
  <div :class="userClass">
    <div class="avatar">
      {{ avatar }}
    </div>
    <div class="content">
      <div class="meta">
        <span>{{ name }}</span>
        <span>{{ createTime ? new Date(createTime).toLocaleString('zh-CN') : '' }}</span>
      </div>
      <div v-if="images && images.length" class="msg-images">
        <a
          v-for="(img, i) in images"
          :key="i"
          :href="chatImageUrl(img)"
          target="_blank"
          rel="noopener noreferrer"
        >
          <img :src="chatImageUrl(img)" class="msg-image" loading="lazy" alt="图片" />
        </a>
      </div>
      <div class="text" v-if="!loading">
        <slot>{{ content }}</slot>
      </div>
      <div v-else class="loading-text">
        <span class="dot"></span>
        <span class="dot"></span>
        <span class="dot"></span>
      </div>
      <div v-if="!loading && sources && sources.length" class="sources">
        <div class="sources-title">🔗 网络来源</div>
        <a
          v-for="(src, i) in sources"
          :key="i"
          class="source-link"
          :href="src.url || '#'"
          target="_blank"
          rel="noopener noreferrer"
        >
          <span class="source-idx">[{{ i + 1 }}]</span>
          <span class="source-name">{{ src.title || src.url }}</span>
        </a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.message-item {
  display: flex;
  margin-bottom: 20px;
}

.message-item.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background-color: #18a058;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 10px;
}

.message-item.user .avatar {
  background-color: #5885f6;
}

.content {
  max-width: 70%;
}

.meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #888;
  margin-bottom: 8px;
}

.text {
  background-color: #f5f5f5;
  padding: 12px 16px;
  border-radius: 8px;
  line-height: 1.6;
  word-wrap: break-word;
  white-space: pre-wrap;
}

.message-item.user .text {
  background-color: #e8f5e9;
}

.message-item.user .meta {
  flex-direction: row-reverse;
}

/* 加载动画 */
.loading-text {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  background-color: #f5f5f5;
  border-radius: 8px;
}

.dot {
  width: 8px;
  height: 8px;
  background-color: #999;
  border-radius: 50%;
  margin: 0 3px;
  animation: bounce 1.4s infinite ease-in-out both;
}

.dot:nth-child(1) { animation-delay: -0.32s; }
.dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.msg-images {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 6px;
}

.msg-image {
  max-width: 220px;
  max-height: 160px;
  border-radius: 8px;
  object-fit: cover;
  border: 1px solid rgba(128, 128, 128, 0.25);
}
</style>

<style scoped>
.sources {
  margin-top: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  background-color: rgba(0, 0, 0, 0.04);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sources-title {
  font-size: 12px;
  color: #888;
}

.source-link {
  font-size: 13px;
  color: #5885f6;
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-link:hover {
  text-decoration: underline;
}

.source-idx {
  color: #888;
  margin-right: 4px;
}

.msg-images {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 6px;
}

.msg-image {
  max-width: 220px;
  max-height: 160px;
  border-radius: 8px;
  object-fit: cover;
  border: 1px solid rgba(128, 128, 128, 0.25);
}
</style>
