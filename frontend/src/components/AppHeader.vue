<template>
  <header class="app-header">
    <div class="header-inner">
      <!-- Logo -->
      <router-link to="/home" class="logo">
        <el-icon :size="24"><Reading /></el-icon>
        <span class="logo-text">BookRec</span>
      </router-link>

      <!-- 导航 -->
      <nav class="nav-links">
        <router-link to="/home" active-class="active">
          <el-icon><House /></el-icon> 首页
        </router-link>
        <router-link to="/books" active-class="active">
          <el-icon><Collection /></el-icon> 图书库
        </router-link>
        <router-link to="/my-ratings" active-class="active">
          <el-icon><Star /></el-icon> 我的评分
        </router-link>
      </nav>

      <!-- 右侧用户区 -->
      <div class="header-right">
        <span class="user-tag">
          <el-icon><User /></el-icon>
          {{ userStore.username }}
        </span>
        <el-button text @click="handleLogout" class="logout-btn">
          <el-icon><SwitchButton /></el-icon>
        </el-button>
      </div>
    </div>
  </header>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { ElMessageBox } from 'element-plus'

const router = useRouter()
const userStore = useUserStore()

function handleLogout() {
  ElMessageBox.confirm('确定要退出登录吗？', '提示', {
    confirmButtonText: '退出',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(() => {
    userStore.logout()
    router.push('/login')
  }).catch(() => {})
}
</script>

<style scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 1000;
  height: 60px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
  box-shadow: 0 1px 8px rgba(107, 66, 38, 0.04);
}
.header-inner {
  max-width: 1280px;
  margin: 0 auto;
  height: 100%;
  display: flex;
  align-items: center;
  padding: 0 20px;
  gap: 32px;
}
.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  color: var(--primary);
  flex-shrink: 0;
}
.logo-text {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 1px;
}
.nav-links {
  display: flex;
  gap: 4px;
  flex: 1;
}
.nav-links a {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  text-decoration: none;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition);
}
.nav-links a:hover {
  color: var(--primary);
  background: rgba(107, 66, 38, 0.06);
}
.nav-links a.active {
  color: var(--primary);
  background: rgba(107, 66, 38, 0.10);
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.user-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 14px;
}
.logout-btn {
  color: var(--text-muted) !important;
}
.logout-btn:hover {
  color: var(--danger) !important;
}
</style>
