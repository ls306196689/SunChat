import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../pages/ChatView.vue'
import MemoriesView from '../pages/MemoriesView.vue'
import KnowledgeView from '../pages/KnowledgeView.vue'
import SettingsView from '../pages/SettingsView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'chat',
      component: ChatView
    },
    {
      path: '/memories',
      name: 'memories',
      component: MemoriesView
    },
    {
      path: '/knowledge',
      name: 'knowledge',
      component: KnowledgeView
    },
    {
      path: '/settings',
      name: 'settings',
      component: SettingsView
    }
  ]
})

export default router
