import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

// 请求实例（LLM 生成为长耗时请求，超时放宽到 5 分钟；流式走 fetch 不受此限制）
const request = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    // 添加时间戳防止缓存
    if (config.method === 'get') {
      config.params = {
        ...config.params,
        _t: Date.now()
      }
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    // 统一错误处理
    if (error.response) {
      const status = error.response.status
      switch (status) {
        case 400:
          console.error('请求参数错误')
          break
        case 401:
          console.error('未授权，请重新登录')
          break
        case 403:
          console.error('拒绝访问')
          break
        case 404:
          console.error('请求资源不存在')
          break
        case 500:
          console.error('服务器错误')
          break
        default:
          console.error(`请求失败: ${status}`)
      }
    } else if (error.code === 'ECONNABORTED') {
      console.error('请求超时')
    } else if (error.code === 'ERR_NETWORK') {
      console.error('网络连接失败，请检查网络或后端服务')
    }
    return Promise.reject(error)
  }
)

export default request

// R-008: 对话图片上传（multipart,不走 JSON 拦截器假设）
export function uploadChatImage(file) {
  const form = new FormData()
  form.append('file', file)
  return request.post('/chat/images', form, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// R-008: 图片回显 URL
export function chatImageUrl(imageId) {
  return `${API_BASE_URL}/chat/images/${encodeURIComponent(imageId)}`
}

// R-009: 语音转写(audio blob → text)
export function transcribeSpeech(blob) {
  const form = new FormData()
  form.append('file', blob, 'recording.webm')
  return request.post('/speech/transcribe', form, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// R-009: ASR 状态(🎤 可用性)
export function speechStatus() {
  return request.get('/speech/status')
}
