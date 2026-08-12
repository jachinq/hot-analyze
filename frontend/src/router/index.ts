import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/Home.vue'),
    },
    {
      path: '/category/:name',
      name: 'category',
      component: () => import('../views/Category.vue'),
      props: true,
    },
    {
      path: '/history',
      name: 'history',
      component: () => import('../views/History.vue'),
    },
  ],
})

export default router
