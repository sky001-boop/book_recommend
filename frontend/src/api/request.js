import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'

const request = axios.create({
    baseURL: '/api',
    timeout: 15000,
})

// 请求拦截器：自动带 JWT Token
request.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token')
        if (token) {
            config.headers.Authorization = `Bearer ${token}`
        }
        return config
    },
    (error) => Promise.reject(error)
)

// 响应拦截器：统一错误处理
request.interceptors.response.use(
    (response) => {
        const data = response.data
        // 如果是下载文件等非 JSON 响应
        if (typeof data !== 'object') return response
        // 业务错误
        if (data.code && data.code !== 200) {
            ElMessage.error(data.message || '请求失败')
            return Promise.reject(new Error(data.message))
        }
        return response
    },
    (error) => {
        if (error.response) {
            const status = error.response.status
            if (status === 401 || status === 403) {
                localStorage.removeItem('token')
                localStorage.removeItem('username')
                ElMessage.error('登录已过期，请重新登录')
                router.push('/login')
            } else if (status === 404) {
                ElMessage.error('资源不存在')
            } else if (status >= 500) {
                ElMessage.error('服务器错误，请稍后重试')
            }
        } else {
            ElMessage.error('网络连接失败')
        }
        return Promise.reject(error)
    }
)

export default request
