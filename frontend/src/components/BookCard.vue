<template>
  <router-link :to="`/book/${book.id}`" class="book-card" @click="onCardClick">
    <!-- 封面 -->
    <div class="book-cover">
      <img
        v-if="book.cover"
        :src="book.cover"
        :alt="book.title"
        @error="onImageError"
      />
      <div v-else class="cover-placeholder">
        <el-icon :size="36"><Reading /></el-icon>
        <span>{{ book.title?.charAt(0) || '书' }}</span>
      </div>
      <!-- 社区均分角标（右上），豆瓣风格 -->
      <span v-if="book.avgRating > 0" class="score-badge">
        <el-icon :size="10"><StarFilled /></el-icon>
        {{ book.avgRating }}
      </span>
      <!-- 分类角标（左上） -->
      <span v-if="book.category" class="category-badge">{{ book.category }}</span>
    </div>

    <!-- 信息 -->
    <div class="book-info">
      <h3 class="book-title" :title="book.title">{{ book.title }}</h3>
      <p class="book-author">{{ book.author || '未知作者' }}</p>
      <p v-if="book.publisher" class="book-publisher">{{ book.publisher }}</p>
    </div>
  </router-link>
</template>

<script setup>
import { ref } from 'vue'
import { reportBehavior } from '../api/behavior'

const props = defineProps({
  book: { type: Object, required: true },
  score: { type: Number, default: undefined },
})

const imgError = ref(false)

function onImageError() {
  imgError.value = true
}

// 点击埋点（fire-and-forget，AB 实验 CTR 统计）
function onCardClick() {
  if (props.book?.id) {
    reportBehavior(props.book.id, 'click').catch(() => {})
  }
}
</script>

<style scoped>
.book-card {
  display: block;
  background: rgba(255,255,255,0.9);
  backdrop-filter: blur(6px);
  border-radius: var(--radius);
  overflow: hidden;
  text-decoration: none;
  border: 1px solid var(--border);
  transition: all var(--transition);
  cursor: pointer;
}
.book-card:hover {
  transform: translateY(-6px) scale(1.02);
  box-shadow: var(--shadow-lg);
  border-color: var(--accent-light);
}

.book-cover {
  position: relative;
  width: 100%;
  aspect-ratio: 3 / 4;
  overflow: hidden;
  background: linear-gradient(135deg, #f5ebe0, #e8d5c0);
}
.book-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--accent);
  gap: 8px;
}
.cover-placeholder span {
  font-size: 24px;
  font-weight: 700;
  color: var(--primary);
}

.score-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  display: flex;
  align-items: center;
  gap: 3px;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(4px);
  color: #FFB800;
  font-size: 12px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 4px;
  z-index: 2;
}

.book-info {
  padding: 12px 14px 14px;
}
.book-title {
  font-size: 14px;
  font-weight: 600;
  font-family: var(--font-serif);
  color: var(--text);
  line-height: 1.4;
  letter-spacing: -0.2px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.book-author {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}
.book-publisher {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

.category-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.9);
  color: var(--primary);
  font-weight: 600;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
  backdrop-filter: blur(4px);
  z-index: 2;
  max-width: calc(100% - 65px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
