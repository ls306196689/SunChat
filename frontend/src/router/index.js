import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../pages/ChatView.vue'
import MemoriesView from '../pages/MemoriesView.vue'
import KnowledgeView from '../pages/KnowledgeView.vue'
import SettingsView from '../pages/SettingsView.vue'
import MobileView from '../pages/MobileView.vue'  // R-014

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
    },
    {
      path: '/m',
      name: 'mobile',
      component: MobileView
    }
  ]
})

export default router
