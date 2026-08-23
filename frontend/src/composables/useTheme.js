import { ref, watch, computed, onMounted } from 'vue'

export function useTheme() {
  const theme = ref('light')
  const isDark = computed(() => theme.value === 'dark')

  function applyTheme(themeName) {
    if (themeName === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }

  function toggleTheme() {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
    applyTheme(theme.value)
    localStorage.setItem('sunchat-theme', theme.value)
  }

  function setTheme(themeName) {
    theme.value = themeName
    applyTheme(themeName)
    localStorage.setItem('sunchat-theme', theme.value)
  }

  onMounted(() => {
    // 从 localStorage 读取主题
    const savedTheme = localStorage.getItem('sunchat-theme')
    if (savedTheme) {
      setTheme(savedTheme)
    } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      setTheme('dark')
    }
  })

  return {
    theme,
    isDark,
    toggleTheme,
    setTheme
  }
}
