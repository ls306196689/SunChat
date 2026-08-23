import { ref, onMounted, onUnmounted, nextTick } from 'vue'

export function useChatScroll(containerRef, messages) {
  const isScrolledToBottom = ref(true)
  const autoScrollEnabled = ref(true)

  function scrollToBottom() {
    nextTick(() => {
      const container = containerRef.value
      if (container) {
        container.scrollTop = container.scrollHeight
      }
    })
  }

  function handleScroll() {
    const container = containerRef.value
    if (!container) return

    const threshold = 50
    const currentPosition = container.scrollTop + container.clientHeight
    const containerScrollHeight = container.scrollHeight

    if (currentPosition >= containerScrollHeight - threshold) {
      isScrolledToBottom.value = true
      if (!autoScrollEnabled.value) {
        autoScrollEnabled.value = true
      }
    } else {
      isScrolledToBottom.value = false
      autoScrollEnabled.value = false
    }
  }

  // 监听消息变化，自动滚动
  function watchMessages() {
    nextTick(() => {
      if (autoScrollEnabled.value) {
        scrollToBottom()
      }
    })
  }

  onMounted(() => {
    const container = containerRef.value
    if (container) {
      container.addEventListener('scroll', handleScroll)
    }
    
    // 初始滚动到底部
    scrollToBottom()
  })

  onUnmounted(() => {
    const container = containerRef.value
    if (container) {
      container.removeEventListener('scroll', handleScroll)
    }
  })

  return {
    isScrolledToBottom,
    autoScrollEnabled,
    scrollToBottom,
    handleScroll,
    watchMessages
  }
}
