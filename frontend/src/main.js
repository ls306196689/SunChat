// R-016: 应用入口埋点(canary 接力)——模块被执行/挂载/失败都要留痕,
// 即使 mobileDiag(router/theme 等 import)本身挂掉也有独立上报通道 __diagSend。
;(function mark() {
  try {
    window.__diagSend && window.__diagSend('entry.import.ok', 'main.js executing')
  } catch (e) {}
})()

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import NaiveUI from 'naive-ui'

import App from './App.vue'
import router from './router'

import './assets/main.css'

const app = createApp(App)

const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(NaiveUI)

app.config.errorHandler = (err, _inst, info) => {
  try {
    window.__diagSend && window.__diagSend('vue.error',
      `${info}: ${(err && err.message) || String(err)}`,
      { stack: String((err && err.stack) || '').slice(0, 400) })
  } catch (e) {}
}

app.mount('#app')
window.__sunchat_entered = true
try {
  window.__diagSend && window.__diagSend('app.mounted', 'vue mounted')
} catch (e) {}
