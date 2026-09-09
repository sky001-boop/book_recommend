<template>
  <div class="page-container">
    <!-- 加载中 -->
    <div v-if="loading" class="detail-skeleton">
      <div class="skeleton" style="width:240px; aspect-ratio:3/4"></div>
      <div class="skeleton-info">
        <div class="skeleton" style="height:28px; width:60%"></div>
        <div class="skeleton" style="height:18px; width:30%; margin-top:12px"></div>
        <div class="skeleton" style="height:14px; width:40%; margin-top:6px"></div>
        <div class="skeleton" style="height:100px; width:100%; margin-top:20px"></div>
      </div>
    </div>

    <!-- 图书详情 -->
    <template v-else-if="book">
      <div class="detail-layout">
        <!-- 封面 -->
        <div class="cover-section">
          <img v-if="book.cover" :src="book.cover" :alt="book.title" class="cover-img" />
          <div v-else class="cover-placeholder">
            <el-icon :size="64"><Reading /></el-icon>
            <span>{{ book.title?.charAt(0) }}</span>
          </div>
        </div>

        <!-- 信息 -->
        <div class="info-section">
          <h1 class="book-title">{{ book.title }}</h1>
          <p class="book-author">作者：{{ book.author || '未知' }}</p>
          <p v-if="book.publisher" class="book-meta">出版社：{{ book.publisher }}</p>
          <p v-if="book.publishYear" class="book-meta">出版年份：{{ book.publishYear }}</p>
          <p v-if="book.isbn" class="book-meta">ISBN：{{ book.isbn }}</p>
          <p v-if="book.description" class="book-desc">{{ book.description }}</p>

          <!-- 评分区 -->
          <div class="rating-area">
            <div class="rating-label">我的评分</div>
            <StarRating
              v-model="myScore"
              :max-stars="10"
              :size="28"
              :readonly="submitting"
              :show-value="true"
            />
            <el-button
              type="primary"
              :loading="submitting"
              :disabled="myScore === 0"
              @click="submitScore"
              style="margin-left: 16px"
            >
              提交评分
            </el-button>
          </div>
          <p v-if="myExistingScore" class="existing-hint">
            你已评分：{{ myExistingScore }} 分，可重新提交
          </p>
        </div>
      </div>
    </template>

    <!-- 未找到 -->
    <div v-else class="empty-state">
      <el-icon :size="48"><Warning /></el-icon>
      <p>图书不存在</p>
    </div>

    <!-- 相似图书 -->
    <section v-if="similarBooks.length > 0" class="similar-section">
      <div class="section-title">
        <el-icon :size="20"><Connection /></el-icon>
        <h2>喜欢这本书的人也喜欢</h2>
      </div>
      <div class="book-grid">
        <BookCard v-for="b in similarBooks" :key="b.id" :book="b" />
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getBookDetail, getSimilarBooks } from '../api/book'
import { getMyRatings, submitRating } from '../api/recommend'
import { ElMessage } from 'element-plus'
import StarRating from '../components/StarRating.vue'
import BookCard from '../components/BookCard.vue'

const route = useRoute()
const book = ref(null)
const similarBooks = ref([])
const loading = ref(true)
const myScore = ref(0)
const myExistingScore = ref(null)
const submitting = ref(false)

onMounted(async () => {
  const id = route.params.id
  try {
    const [detailRes, similarRes] = await Promise.all([
      getBookDetail(id),
      getSimilarBooks(id, 6),
    ])
    book.value = detailRes.data.data
    similarBooks.value = similarRes.data.data || []
    // 获取用户已有评分
    const rRes = await getMyRatings()
    const ratings = rRes.data.data || []
    const found = ratings.find(r => r.bookId === Number(id))
    if (found) {
      myExistingScore.value = found.score
      myScore.value = found.score
    }
  } catch (e) {}
  finally { loading.value = false }
})

async function submitScore() {
  if (myScore.value < 1 || myScore.value > 10) {
    ElMessage.warning('评分范围为 1-10')
    return
  }
  submitting.value = true
  try {
    await submitRating(book.value.id, myScore.value)
    ElMessage.success('评分成功')
    myExistingScore.value = myScore.value
  } catch (e) {}
  finally { submitting.value = false }
}
</script>

<style scoped>
.detail-layout {
  display: flex;
  gap: 40px;
  background: rgba(255,255,255,0.88);
  backdrop-filter: blur(8px);
  border-radius: var(--radius);
  padding: 36px;
  box-shadow: var(--shadow);
}
.cover-section {
  flex-shrink: 0;
  width: 240px;
}
.cover-img {
  width: 100%;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.12);
}
.cover-placeholder {
  width: 100%;
  aspect-ratio: 3/4;
  background: linear-gradient(135deg, #f5ebe0, #e8d5c0);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--accent);
  gap: 12px;
}
.cover-placeholder span {
  font-size: 28px;
  font-weight: 700;
  color: var(--primary);
}

.info-section {
  flex: 1;
  min-width: 0;
}
.book-title {
  font-size: 26px;
  font-weight: 700;
  font-family: var(--font-serif);
  line-height: 1.3;
  color: var(--text);
}
.book-author {
  font-size: 16px;
  color: var(--accent);
  margin-top: 10px;
  font-weight: 500;
}
.book-meta {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 4px;
}
.book-desc {
  margin-top: 18px;
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.8;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.rating-area {
  display: flex;
  align-items: center;
  margin-top: 24px;
  padding: 20px;
  background: var(--bg);
  border-radius: 10px;
}
.rating-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-right: 12px;
}
.existing-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 8px;
}

.detail-skeleton {
  display: flex;
  gap: 40px;
}
.skeleton-info {
  flex: 1;
}
.empty-state {
  text-align: center;
  padding: 80px 20px;
  color: var(--text-muted);
}

.similar-section {
  margin-top: 36px;
}
.similar-section .section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--primary);
  margin-bottom: 18px;
  padding-bottom: 12px;
  border-bottom: 2px solid var(--border);
}
.similar-section .section-title h2 {
  font-size: 18px;
  font-weight: 700;
  color: var(--text);
}
.similar-section .book-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 16px;
  position: relative;
  z-index: 1;
}
</style>
