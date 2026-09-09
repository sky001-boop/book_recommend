import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
    {
        path: '/',
        redirect: '/home',
    },
    {
        path: '/login',
        name: 'Login',
        component: () => import('../views/LoginView.vue'),
    },
    {
        path: '/home',
        name: 'Home',
        component: () => import('../views/HomeView.vue'),
        meta: { requiresAuth: true },
    },
    {
        path: '/books',
        name: 'BookList',
        component: () => import('../views/BookListView.vue'),
        meta: { requiresAuth: true },
    },
    {
        path: '/book/:id',
        name: 'BookDetail',
        component: () => import('../views/BookDetailView.vue'),
        meta: { requiresAuth: true },
    },
    {
        path: '/my-ratings',
        name: 'MyRatings',
        component: () => import('../views/MyRatingsView.vue'),
        meta: { requiresAuth: true },
    },
]

const router = createRouter({
    history: createWebHashHistory(),
    routes,
})

// 路由守卫：未登录跳转登录页
router.beforeEach((to, from, next) => {
    const token = localStorage.getItem('token')
    if (to.meta.requiresAuth && !token) {
        next('/login')
    } else if (to.path === '/login' && token) {
        next('/home')
    } else {
        next()
    }
})

export default router
