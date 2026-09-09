<template>
  <div class="page-container">
    <div class="page-header">
      <h1>我的评分</h1>
      <p>共 {{ ratings.length }} 条评分记录</p>
    </div>

    <!-- 加载 -->
    <div v-if="loading" class="loading-wrap">
      <el-icon :size="32" class="is-loading"><Loading /></el-icon>
    </div>

    <!-- 空 -->
    <div v-else-if="ratings.length === 0" class="empty-state">
      <el-icon :size="48"><Star /></el-icon>
      <p>还没有评分记录</p>
      <el-button type="primary" @click="$router.push('/books')">去评分</el-button>
    </div>

    <!-- 评分列表 -->
    <div v-else class="rating-list">
      <div
        v-for="r in ratings"
        :key="r.id"
        class="rating-item"
        @click="$router.push(`/book/${r.bookId}`)"
      >
        <div class="rating-left">
          <span class="rating-score">{{ r.score }}</span>
          <span class="rating-unit">分</span>
        </div>
        <div class="rating-mid">
          <p class="rating-book-title">{{ bookNames[r.bookId] || `图书 #${r.bookId}` }}</p>
          <p class="rating-time">{{ formatTime(r.createTime) }}</p>
        </div>
        <div class="rating-right">
          <StarRating :model-value="r.score" :max-stars="10" readonly :size="14" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getMyRatings } from '../api/recommend'
import { getBookList } from '../api/book'
import StarRating from '../components/StarRating.vue'

const ratings = ref([])
const bookNames = ref({})
const loading = ref(true)

onMounted(async () => {
  try {
    const [rRes, bRes] = await Promise.all([
      getMyRatings(),
      getBookList(),
    ])
    ratings.value = rRes.data.data || []
    const books = bRes.data.data || []
    books.forEach(b => { bookNames.value[b.id] = b.title })
  } catch (e) {}
  finally { loading.value = false }
})

function formatTime(t) {
  if (!t) return ''
  return new Date(t).toLocaleDateString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}
</script>

<style scoped>
.loading-wrap {
  text-align: center;
  padding: 60px;
  color: var(--primary);
}
.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-muted);
}
.empty-state p {
  margin: 16px 0 20px;
  font-size: 14px;
}

.rating-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.rating-item {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 18px 20px;
  background: rgba(255,255,255,0.88);
  backdrop-filter: blur(6px);
  border-radius: 10px;
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all var(--transition);
}
.rating-item:hover {
  box-shadow: var(--shadow);
  border-color: var(--accent-light);
}
.rating-left {
  display: flex;
  align-items: baseline;
  gap: 2px;
  min-width: 60px;
}
.rating-score {
  font-size: 28px;
  font-weight: 800;
  color: var(--accent);
}
.rating-unit {
  font-size: 14px;
  color: var(--text-muted);
}
.rating-mid {
  flex: 1;
}
.rating-book-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}
.rating-time {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}
</style>
