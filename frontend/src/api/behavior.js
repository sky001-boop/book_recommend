import request from './request'

// 行为埋点：type = exposure / click / rating
export function reportBehavior(bookId, type) {
    return request.post('/behavior/report', { bookId, type })
}
