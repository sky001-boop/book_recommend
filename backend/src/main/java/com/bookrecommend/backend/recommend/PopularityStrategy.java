package com.bookrecommend.backend.recommend;

import com.bookrecommend.backend.entity.Rating;
import com.bookrecommend.backend.mapper.RatingMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.ZSetOperations;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.stream.Collectors;

/**
 * Popularity: 热门推荐（冷启动兜底方案）
 *
 * 原理：
 * 1. 统计每本书的被评分次数
 * 2. 按评分次数降序取 Top-N
 * 3. 结果存入 Redis Sorted Set 加速读取
 */
@Component
@RequiredArgsConstructor
public class PopularityStrategy implements RecommendStrategy {

    private final RatingMapper ratingMapper;
    private final RedisTemplate<String, Object> redisTemplate;

    private static final String REDIS_KEY = "brs:hot:books";

    @Override
    public List<ScoredBook> recommend(Long userId, int topN) {
        // 排除该用户已评分的书
        Set<Long> rated = ratingMapper.findByUserId(userId).stream()
                .map(Rating::getBookId).collect(Collectors.toSet());
        return getHotBooks(topN, rated);
    }

    /**
     * 获取热门图书（排除指定 ID 列表）
     */
    public List<ScoredBook> getHotBooks(int topN) {
        return getHotBooks(topN, Collections.emptySet());
    }

    public List<ScoredBook> getHotBooks(int topN, Set<Long> excludeIds) {

        // 多拉 3 倍以保证过滤后还有足够的
        int fetchSize = Math.max(topN * 3, topN + excludeIds.size() * 2);
        List<ScoredBook> all;

        // 先查 Redis
        Set<ZSetOperations.TypedTuple<Object>> cached =
                redisTemplate.opsForZSet().reverseRangeWithScores(REDIS_KEY, 0, fetchSize - 1);

        if (cached != null && !cached.isEmpty()) {
            all = cached.stream()
                    .map(t -> new ScoredBook(
                            ((Number) t.getValue()).longValue(),
                            t.getScore()))
                    .collect(Collectors.toList());
        } else {
            // 缓存未命中，从 MySQL 计算
            all = computeHotBooks(fetchSize);
            for (ScoredBook sb : all) {
                redisTemplate.opsForZSet().add(REDIS_KEY, sb.getBookId(), sb.getScore());
            }
        }

        // 排除已评分的书
        if (!excludeIds.isEmpty()) {
            all = all.stream()
                    .filter(b -> !excludeIds.contains(b.getBookId()))
                    .limit(topN)
                    .collect(Collectors.toList());
        } else if (all.size() > topN) {
            all = all.subList(0, topN);
        }

        return all;

    }

    /**
     * 从评分表统计热门书
     */
    private List<ScoredBook> computeHotBooks(int topN) {

        List<Rating> allRatings = ratingMapper.findAll();

        // 统计每本书的评分次数
        Map<Long, Long> counts = new HashMap<>();
        for (Rating r : allRatings) {
            counts.merge(r.getBookId(), 1L, Long::sum);
        }

        return counts.entrySet().stream()
                .sorted((a, b) -> Long.compare(b.getValue(), a.getValue()))
                .limit(topN)
                .map(e -> new ScoredBook(e.getKey(), e.getValue().doubleValue()))
                .collect(Collectors.toList());

    }

    /**
     * 重建热门缓存（定时任务调用）
     */
    public void refreshCache() {
        redisTemplate.delete(REDIS_KEY);
        List<ScoredBook> hot = computeHotBooks(100);
        for (ScoredBook sb : hot) {
            redisTemplate.opsForZSet().add(REDIS_KEY, sb.getBookId(), sb.getScore());
        }
    }

    @Override
    public String name() {
        return "Popularity";
    }

}
