<template>
  <div class="home-page">
    <!-- 欢迎横幅 -->
    <section class="hero">
      <div class="hero-bg"></div>
      <div class="hero-inner">
        <p class="hero-greeting">Welcome back</p>
        <h1 class="hero-name">{{ userStore.username }}</h1>
        <p class="hero-quote">" 每本好书，都是通往另一个世界的门 "</p>
      </div>
    </section>

    <div class="page-container">
      <!-- 自然语言找书（RAG 语义检索） -->
      <section class="section nl-search">
        <div class="section-header">
          <div class="section-title">
            <el-icon :size="22"><ChatDotRound /></el-icon>
            <h2>自然语言找书</h2>
          </div>
          <span class="section-badge">RAG 语义检索 + LLM</span>
        </div>
        <div class="search-box">
          <el-input
            v-model="nlQuery"
            placeholder="试试：推荐几本像《1984》那样反乌托邦的书"
            size="large"
            clearable
            @keyup.enter="doSearch"
          >
            <template #append>
              <el-button type="primary" :loading="searchLoading" @click="doSearch">
                <el-icon><Search /></el-icon>&nbsp;语义搜索
              </el-button>
            </template>
          </el-input>
        </div>
        <div v-if="nlAnswer" class="nl-answer">
          <el-icon><MagicStick /></el-icon>
          <span>{{ nlAnswer }}</span>
        </div>
        <div v-if="nlBooks.length" class="book-grid">
          <BookCard
            v-for="item in nlBooks"
            :key="item.id"
            :book="item"
          />
        </div>
        <div v-else-if="nlSearched" class="empty-state">
          <p>没有找到相关图书，换个说法试试</p>
        </div>
      </section>

      <!-- 猜你喜欢 -->
      <section class="section">
        <div class="section-header">
          <div class="section-title">
            <el-icon :size="22"><MagicStick /></el-icon>
            <h2>猜你喜欢</h2>
          </div>
          <span class="section-badge">AI 个性化推荐 · {{ abGroup ? abGroup + '组' : '' }}</span>
        </div>

        <!-- 加载中 -->
        <div v-if="personalLoading" class="book-grid">
          <div v-for="i in 6" :key="i" class="skeleton-card">
            <div class="skeleton" style="aspect-ratio:3/4; width:100%"></div>
            <div class="skeleton" style="height:18px; width:80%; margin-top:10px"></div>
            <div class="skeleton" style="height:14px; width:50%; margin-top:6px"></div>
          </div>
        </div>

        <!-- 推荐为空 -->
        <div v-else-if="personalBooks.length === 0" class="empty-state">
          <el-icon :size="48"><Sunny /></el-icon>
          <p>评分一些图书后，这里会出现专属于你的推荐</p>
          <el-button type="primary" @click="$router.push('/books')">去逛逛图书库</el-button>
        </div>

        <!-- 推荐列表 -->
        <div v-else class="book-grid">
          <BookCard
            v-for="item in personalBooks"
            :key="item.id"
            :book="item"
          />
        </div>
      </section>

      <!-- 热门推荐 -->
      <section class="section">
        <div class="section-header">
          <div class="section-title">
            <el-icon :size="22"><TrendCharts /></el-icon>
            <h2>热门推荐</h2>
          </div>
          <div class="hot-actions">
            <span class="section-badge hot">全站热门</span>
            <el-button text size="small" @click="refreshHot" :loading="hotLoading" class="refresh-btn">
              <el-icon><Refresh /></el-icon> 换一批
            </el-button>
          </div>
        </div>

        <div v-if="hotLoading" class="book-grid">
          <div v-for="i in 6" :key="i" class="skeleton-card">
            <div class="skeleton" style="aspect-ratio:3/4; width:100%"></div>
            <div class="skeleton" style="height:18px; width:80%; margin-top:10px"></div>
            <div class="skeleton" style="height:14px; width:50%; margin-top:6px"></div>
          </div>
        </div>

        <div v-else class="book-grid">
          <BookCard
            v-for="item in hotBooks"
            :key="item.id"
            :book="item"
          />
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useUserStore } from '../stores/user'
import { getRecommendAB, getHotRecommend } from '../api/recommend'
import { reportBehavior } from '../api/behavior'
import { naturalLanguageSearch } from '../api/search'
import BookCard from '../components/BookCard.vue'

const userStore = useUserStore()

const personalBooks = ref([])
const hotBooks = ref([])
const personalLoading = ref(false)   // 初始不闪骨架
const hotLoading = ref(false)
const hotPage = ref(0)

// AB 实验分组（userId % 2 分桶：A=混合加权, B=双塔+DeepFM）
const abGroup = ref('')
const abStrategy = ref('')

// 自然语言找书
const nlQuery = ref('')
const nlBooks = ref([])
const nlAnswer = ref('')
const nlSearched = ref(false)
const searchLoading = ref(false)

// 延迟显示骨架：200ms 内数据到了就不闪
let personalTimer = null
let hotTimer = null

// 埋点：曝光（fire-and-forget，不阻塞渲染）
function logExposure(bookIds) {
  if (!bookIds || !bookIds.length) return
  bookIds.slice(0, 10).forEach(id => {
    reportBehavior(id, 'exposure').catch(() => {})
  })
}

async function loadHot(showLoading = true) {
  if (showLoading) hotTimer = setTimeout(() => { hotLoading.value = true }, 200)
  try {
    const res = await getHotRecommend(10, hotPage.value * 10)
    hotBooks.value = res.data.data || []
  } catch (e) {}
  finally {
    if (showLoading) {
      clearTimeout(hotTimer)
      hotLoading.value = false
    }
  }
}

function refreshHot() {
  hotPage.value = (hotPage.value + 1) % 5   // 0~4 循环，最多翻 5 批
  loadHot(false)
}

async function doSearch() {
  const q = nlQuery.value?.trim()
  if (!q || searchLoading.value) return
  searchLoading.value = true
  nlSearched.value = true
  try {
    const res = await naturalLanguageSearch(q)
    nlBooks.value = res.data.data || []
    nlAnswer.value = res.data.answer || ''
  } catch (e) {
    nlBooks.value = []
    nlAnswer.value = ''
  } finally {
    searchLoading.value = false
  }
}

onMounted(async () => {
  personalTimer = setTimeout(() => { personalLoading.value = true }, 200)
  try {
    const [pRes] = await Promise.all([
      getRecommendAB(10),
      loadHot(),
    ])
    personalBooks.value = pRes.data.data || []
    abGroup.value = pRes.data.group || ''
    abStrategy.value = pRes.data.strategy || ''
    // AB 实验埋点：曝光上报
    logExposure(personalBooks.value.map(b => b.id))
  } catch (e) {}
  finally {
    clearTimeout(personalTimer)
    personalLoading.value = false
  }
})
</script>

<style scoped>
.hero {
  position: relative;
  min-height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  overflow: hidden;
}
.hero-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 100% 100% at 50% 100%, #3E1F0D 0%, #5C3317 40%, #7D5A1E 70%, #A0782C 100%),
    repeating-linear-gradient(30deg, transparent, transparent 30px, rgba(255,255,255,0.02) 30px, rgba(255,255,255,0.02) 31px);
  z-index: 0;
}
.hero-inner {
  position: relative;
  z-index: 1;
  color: #fff;
  padding: 36px 20px;
}
.hero-greeting {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 4px;
  opacity: 0.55;
  margin-bottom: 6px;
  font-weight: 500;
}
.hero-name {
  font-size: 34px;
  font-weight: 700;
  font-family: var(--font-serif);
  letter-spacing: 2px;
  margin-bottom: 10px;
  text-shadow: 0 2px 20px rgba(0,0,0,0.2);
}
.hero-quote {
  font-size: 14px;
  font-style: italic;
  opacity: 0.65;
  font-family: var(--font-serif);
  letter-spacing: 1px;
}

.section {
  margin-bottom: 40px;
}
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  padding-bottom: 14px;
  border-bottom: 2px solid var(--border);
}
.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--primary);
}
.section-title h2 {
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
}
.section-badge {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 20px;
  background: rgba(107, 66, 38, 0.08);
  color: var(--primary);
  font-weight: 600;
}
.section-badge.hot {
  background: rgba(184, 134, 11, 0.10);
  color: var(--accent);
}

.hot-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.nl-search .search-box {
  margin-bottom: 16px;
}
.nl-answer {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  background: rgba(107, 66, 38, 0.06);
  border-left: 3px solid var(--primary);
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 20px;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.7;
}
.refresh-btn {
  color: var(--text-secondary) !important;
  font-size: 13px;
}
.refresh-btn:hover {
  color: var(--accent) !important;
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

.skeleton-card {
  background: var(--bg-card);
  border-radius: var(--radius);
  padding: 0;
}
</style>
