<template>
  <div class="page-container">
    <div class="page-header">
      <h1>图书库</h1>
      <p>共 {{ total }} 本图书</p>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <el-input
        v-model="keyword"
        placeholder="搜索书名、作者..."
        clearable
        prefix-icon="Search"
        size="large"
        class="search-input"
      />
      <el-select v-model="category" placeholder="全部分类" clearable style="width:140px">
        <el-option v-for="c in allCategories" :key="c" :label="c" :value="c" />
      </el-select>
    </div>

    <!-- 加载 -->
    <div v-if="loading" class="book-grid">
      <div v-for="i in 8" :key="i" class="skeleton-card">
        <div class="skeleton" style="aspect-ratio:3/4; width:100%"></div>
        <div class="skeleton" style="height:18px; width:80%; margin-top:10px"></div>
        <div class="skeleton" style="height:14px; width:50%; margin-top:6px"></div>
      </div>
    </div>

    <!-- 图书列表 -->
    <div v-else class="book-grid">
      <BookCard v-for="book in filteredBooks" :key="book.id" :book="book" />
    </div>

    <!-- 分页 -->
    <div v-if="!loading && total > 0" class="pagination-wrap">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        background
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { getBookList } from '../api/book'
import BookCard from '../components/BookCard.vue'

const allBooks = ref([])
const allCategories = ref([])
const total = ref(0)
const loading = ref(true)

const keyword = ref('')
const category = ref('')
const page = ref(1)
const pageSize = 24

async function fetchBooks() {
  loading.value = true
  try {
    const res = await getBookList(page.value, pageSize, keyword.value, category.value)
    allBooks.value = res.data.data || []
    total.value = res.data.total || 0
    // 固定分类列表，不拉 10K 图书
    allCategories.value = ['传记回忆录','励志自助','历史','历史小说','哲学','商业经济','奇幻','宗教灵性','小说','少儿','恐怖','推理悬疑','文学经典','漫画绘本','爱情','科幻','科普','计算机技术','诗歌戏剧']
  } catch (e) {}
  finally { loading.value = false }
}

onMounted(fetchBooks)

const filteredBooks = computed(() => allBooks.value)

watch([keyword, category], () => {
  page.value = 1
  fetchBooks()
})

watch(page, () => {
  fetchBooks()
})
</script>

<style scoped>
.search-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}
.search-input {
  max-width: 400px;
}
.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: 36px;
  padding-bottom: 40px;
}
</style>
