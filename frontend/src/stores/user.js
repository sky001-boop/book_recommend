import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, register as registerApi } from '../api/auth'

export const useUserStore = defineStore('user', () => {
    const token = ref(localStorage.getItem('token') || '')
    const username = ref(localStorage.getItem('username') || '')

    const isLoggedIn = computed(() => !!token.value)

    async function login(usernameVal, password) {
        const res = await loginApi(usernameVal, password)
        const data = res.data
        token.value = data.token
        username.value = usernameVal
        localStorage.setItem('token', data.token)
        localStorage.setItem('username', usernameVal)
    }

    async function register(usernameVal, password, email) {
        await registerApi(usernameVal, password, email)
    }

    function logout() {
        token.value = ''
        username.value = ''
        localStorage.removeItem('token')
        localStorage.removeItem('username')
    }

    return { token, username, isLoggedIn, login, register, logout }
})
