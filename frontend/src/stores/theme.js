import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  const theme = ref(document.documentElement.classList.contains('dark') ? 'dark' : 'light')

  const isDark = computed(() => theme.value === 'dark')

  function toggleTheme() {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
    applyTheme(theme.value)
  }

  function applyTheme(themeName) {
    if (themeName === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }

  function setTheme(themeName) {
    theme.value = themeName
    applyTheme(themeName)
  }

  // 初始化主题
  function initTheme() {
    const savedTheme = localStorage.getItem('sunchat-theme')
    if (savedTheme) {
      setTheme(savedTheme)
    } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      setTheme('dark')
    } else {
      setTheme('light')
    }
  }

  return {
    theme,
    isDark,
    toggleTheme,
    setTheme,
    initTheme
  }
})
