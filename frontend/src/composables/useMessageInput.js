import { ref, onMounted, onUnmounted } from 'vue'

export function useMessageInput(inputRef, onSend) {
  const isShiftPressed = ref(false)

  function handleKeyDown(event) {
    if (event.key === 'Shift') {
      isShiftPressed.value = true
    }
  }

  function handleKeyUp(event) {
    if (event.key === 'Shift') {
      isShiftPressed.value = false
    }
  }

  function isEnterWithoutShift(event) {
    return event.key === 'Enter' && !event.shiftKey
  }

  function handleEnterSend(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (onSend && typeof onSend === 'function') {
        onSend()
      }
    }
  }

  onMounted(() => {
    document.addEventListener('keydown', handleKeyDown)
    document.addEventListener('keyup', handleKeyUp)
  })

  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeyDown)
    document.removeEventListener('keyup', handleKeyUp)
  })

  return {
    isShiftPressed,
    handleKeyDown,
    handleKeyUp,
    isEnterWithoutShift,
    handleEnterSend
  }
}
