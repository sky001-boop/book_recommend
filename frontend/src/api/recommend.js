import request from './request'

export function getMyRecommend(topN = 20) {
    return request.get('/recommend/my', { params: { topN } })
}

// AB 实验推荐：返回 data + group(A/B) + strategy
export function getRecommendAB(topN = 20) {
    return request.get('/recommend/ab', { params: { topN } })
}

// 深度学习推荐链路 v2：双塔召回 + DeepFM 精排
export function getRecommendV2(topN = 20) {
    return request.get('/recommend/v2', { params: { topN } })
}

// v2 推荐 + LLM 个性化推荐理由
export function getRecommendExplain(topN = 10) {
    return request.get('/recommend/v2/explain', { params: { topN } })
}

export function getHotRecommend(topN = 20, offset = 0) {
    return request.get('/recommend/hot', { params: { topN, offset } })
}

export function submitRating(bookId, score) {
    return request.post('/rating/submit', { bookId, score })
}

export function getMyRatings() {
    return request.get('/rating/my')
}
