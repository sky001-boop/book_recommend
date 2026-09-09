<template>
  <div class="login-page">
    <!-- 左侧品牌区 -->
    <div class="brand-panel">
      <div class="brand-content">
        <div class="brand-logo">
          <el-icon :size="48"><MagicStick /></el-icon>
        </div>
        <h1 class="brand-name">BookRec</h1>
        <p class="brand-tagline">基于协同过滤的智能图书推荐系统</p>
        <div class="brand-features">
          <div class="feature-item">
            <span class="feature-num">01</span>
            <span>协同过滤 + 用户画像，多算法融合</span>
          </div>
          <div class="feature-item">
            <span class="feature-num">02</span>
            <span>22,808 本真实图书，184K 真实评分</span>
          </div>
          <div class="feature-item">
            <span class="feature-num">03</span>
            <span>毫秒级智能推荐，越评越懂你</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧表单区 -->
    <div class="form-panel">
      <div class="form-card">
        <div class="tabs">
          <button
            :class="{ active: mode === 'login' }"
            @click="mode = 'login'; loginError=''; regError=''"
          >登录</button>
          <button
            :class="{ active: mode === 'register' }"
            @click="mode = 'register'; loginError=''; regError=''"
          >注册</button>
        </div>

        <transition name="fade" mode="out-in">
          <form v-if="mode === 'login'" key="login" @submit.prevent="handleLogin" class="form">
            <div class="form-item">
              <el-input
                v-model="loginForm.username"
                placeholder="用户名"
                prefix-icon="User"
                size="large"
              />
            </div>
            <div class="form-item">
              <el-input
                v-model="loginForm.password"
                type="password"
                placeholder="密码"
                prefix-icon="Lock"
                size="large"
                show-password
                @keyup.enter="handleLogin"
              />
            </div>
            <el-alert v-if="loginError" :title="loginError" type="error" show-icon :closable="false" style="margin-bottom:-8px" />
            <el-button type="primary" size="large" native-type="submit" :loading="loading" class="submit-btn">登 录</el-button>
          </form>

          <form v-else key="register" @submit.prevent="handleRegister" class="form">
            <div class="form-item">
              <el-input v-model="regForm.username" placeholder="用户名" prefix-icon="User" size="large" />
            </div>
            <div class="form-item">
              <el-input v-model="regForm.email" placeholder="邮箱" prefix-icon="Message" size="large" />
            </div>
            <div class="form-item">
              <el-input v-model="regForm.password" type="password" placeholder="密码（至少6位）" prefix-icon="Lock" size="large" show-password />
            </div>
            <el-alert v-if="regError" :title="regError" type="error" show-icon :closable="false" style="margin-bottom:-8px" />
            <el-button type="primary" size="large" native-type="submit" :loading="loading" class="submit-btn">注 册</el-button>
          </form>
        </transition>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { ElMessage } from 'element-plus'

const router = useRouter()
const userStore = useUserStore()

const mode = ref('login')
const loading = ref(false)
const loginError = ref('')
const regError = ref('')

const loginForm = reactive({ username: '', password: '' })
const regForm = reactive({ username: '', password: '', email: '' })

async function handleLogin() {
  loginError.value = ''
  if (!loginForm.username || !loginForm.password) {
    loginError.value = '请填写用户名和密码'
    return
  }
  loading.value = true
  try {
    await userStore.login(loginForm.username, loginForm.password)
    ElMessage.success('登录成功')
    router.push('/home')
  } catch (e) {
    loginError.value = '用户名或密码错误'
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  regError.value = ''
  if (!regForm.username || !regForm.email) {
    regError.value = '请填写用户名和邮箱'
    return
  }
  if (!regForm.password || regForm.password.length < 6) {
    regError.value = '密码至少6位'
    return
  }
  loading.value = true
  try {
    await userStore.register(regForm.username, regForm.password, regForm.email)
    ElMessage.success('注册成功，请登录')
    mode.value = 'login'
    loginForm.username = regForm.username
    regError.value = ''
  } catch (e) {
    regError.value = '注册失败，用户名可能已存在'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  display: flex;
  min-height: 100vh;
}

/* 左侧品牌区 */
.brand-panel {
  flex: 1;
  background: linear-gradient(160deg, #3E1F0D 0%, #5C3317 35%, #7D5A1E 65%, #A0782C 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}
.brand-panel::before {
  content: '';
  position: absolute;
  inset: 0;
  background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.05'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
}

.brand-content {
  position: relative;
  z-index: 1;
  text-align: center;
  color: #fff;
  padding: 60px 50px;
}
.brand-logo {
  font-size: 56px;
  margin-bottom: 20px;
}
.brand-name {
  font-size: 52px;
  font-weight: 800;
  font-family: var(--font-serif);
  letter-spacing: 8px;
  margin-bottom: 14px;
  color: #FFE8C8;
  text-shadow: 0 2px 12px rgba(0,0,0,0.3);
}
.brand-tagline {
  font-size: 15px;
  opacity: 0.55;
  margin-bottom: 56px;
  letter-spacing: 2px;
}
.brand-features {
  display: flex;
  flex-direction: column;
  gap: 18px;
  align-items: flex-start;
  margin: 0 auto;
  width: fit-content;
}
.feature-item {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 13.5px;
  opacity: 0.65;
}
.feature-num {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--accent-light);
  opacity: 0.7;
  min-width: 20px;
}

/* 右侧表单区 */
.form-panel {
  flex: 0.8;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
}
.form-card {
  width: 400px;
  padding: 48px 44px;
  background: var(--bg-card);
  border-radius: 16px;
  box-shadow: 0 4px 40px rgba(0, 0, 0, 0.06);
}
.tabs {
  display: flex;
  margin-bottom: 36px;
  background: var(--bg);
  border-radius: 10px;
  padding: 4px;
}
.tabs button {
  flex: 1;
  padding: 10px;
  border: none;
  background: transparent;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 8px;
  transition: all var(--transition);
}
.tabs button.active {
  background: var(--primary);
  color: #fff;
  box-shadow: 0 2px 8px rgba(107, 66, 38, 0.3);
}
.form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.submit-btn {
  width: 100%;
  height: 46px !important;
  font-size: 16px !important;
  letter-spacing: 4px !important;
  margin-top: 4px;
}
.hint {
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 768px) {
  .brand-panel { display: none; }
  .form-card { width: 90vw; padding: 32px 24px; }
}
</style>
