import request from './request'

// 自然语言找书（RAG 语义检索）
export function naturalLanguageSearch(q) {
    return request.get('/search/nl', { params: { q } })
}
