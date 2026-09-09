import request from './request'

export function getBookList(page = 1, size = 24, keyword = '', category = '') {
    return request.get('/book/list', { params: { page, size, keyword, category } })
}

export function getBookDetail(id) {
    return request.get(`/book/${id}`)
}

export function getSimilarBooks(id, topN = 6) {
    return request.get(`/book/${id}/similar`, { params: { topN } })
}
