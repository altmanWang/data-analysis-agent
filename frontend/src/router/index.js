import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/session/new' },
  {
    path: '/session/:id',
    component: () => import('../components/ChatPanel.vue'),
    props: true,
  },
]

export default createRouter({ history: createWebHistory(), routes })
