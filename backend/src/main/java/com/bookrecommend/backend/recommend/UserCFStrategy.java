package com.bookrecommend.backend.recommend;

import com.bookrecommend.backend.entity.Rating;
import com.bookrecommend.backend.mapper.RatingMapper;
import com.bookrecommend.backend.service.UserSimilarityService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.stream.Collectors;

/**
 * UserCF: 基于用户的协同过滤（邻居预计算版）
 *
 * 快速路径：Redis 读预计算邻居 → 加权聚合 → 返回（~200ms）
 * 慢速路径：全量余弦计算（约 8s，邻居缓存未就绪时使用）
 */
@Component
@RequiredArgsConstructor
public class UserCFStrategy implements RecommendStrategy {

    private final RatingMapper ratingMapper;
    private final UserSimilarityService similarityService;

    private static final int K = 50;

    @Override
    public List<ScoredBook> recommend(Long userId, int topN) {

        // 1. 尝试从 Redis 读预计算的邻居
        Map<Long, Double> neighbors = similarityService.getNeighbors(userId);

        if (neighbors != null && !neighbors.isEmpty()) {
            // ===== 快速路径：读邻居 =====
            return recommendFast(userId, topN, neighbors);
        } else {
            // ===== 慢速路径：在线算 =====
            return recommendSlow(userId, topN);
        }

    }

    /**
     * 快速路径：只加载目标用户 + 邻居的评分（不全量）
     */
    private List<ScoredBook> recommendFast(Long userId, int topN, Map<Long, Double> neighbors) {

        // 构建要查询的用户列表：目标用户 + 所有邻居
        List<Long> userIds = new ArrayList<>(neighbors.keySet());
        userIds.add(userId);

        // 只加载这些用户的评分（~95邻居 × 12条/人 = ~1200条，远小于 184K）
        List<Rating> ratings = ratingMapper.findByUserIds(userIds);

        // user→(book,score)
        Map<Long, Map<Long, Double>> userMatrix = new HashMap<>();
        Map<Long, Double> targetRatings = new HashMap<>();

        for (Rating r : ratings) {
            userMatrix.computeIfAbsent(r.getUserId(), k -> new HashMap<>())
                    .put(r.getBookId(), r.getScore().doubleValue());
            if (r.getUserId().equals(userId)) {
                targetRatings.put(r.getBookId(), r.getScore().doubleValue());
            }
        }

        // 邻居加权聚合
        Map<Long, Double> scores = new HashMap<>();
        double simSum = 0;

        for (Map.Entry<Long, Double> neighbor : neighbors.entrySet()) {
            Long neighborId = neighbor.getKey();
            double sim = neighbor.getValue();
            simSum += sim;

            Map<Long, Double> neighborRatings = userMatrix.get(neighborId);
            if (neighborRatings == null) continue;

            for (Map.Entry<Long, Double> entry : neighborRatings.entrySet()) {
                Long bookId = entry.getKey();
                if (targetRatings.containsKey(bookId)) continue;
                scores.merge(bookId, entry.getValue() * sim, Double::sum);
            }
        }

        // 除以总相似度（归一化）
        if (simSum > 0) {
            for (Long bookId : scores.keySet()) {
                scores.put(bookId, scores.get(bookId) / simSum);
            }
        }

        return scores.entrySet().stream()
                .sorted((a, b) -> Double.compare(b.getValue(), a.getValue()))
                .limit(topN)
                .map(e -> new ScoredBook(e.getKey(), e.getValue()))
                .collect(Collectors.toList());

    }

    /**
     * 慢速路径：在线计算所有余弦相似度（预计算未就绪时使用）
     */
    private List<ScoredBook> recommendSlow(Long userId, int topN) {

        List<Rating> allRatings = ratingMapper.findAll();

        Map<Long, Map<Long, Double>> matrix = buildMatrix(allRatings);
        Map<Long, Double> targetRatings = matrix.getOrDefault(userId, Collections.emptyMap());
        if (targetRatings.isEmpty()) return Collections.emptyList();

        // 计算与所有用户的相似度
        Map<Long, Double> similarities = new HashMap<>();
        for (Long otherId : matrix.keySet()) {
            if (otherId.equals(userId)) continue;
            double sim = cosineSimilarity(targetRatings, matrix.get(otherId));
            if (sim > 0) similarities.put(otherId, sim);
        }

        // Top-K 邻居
        List<Map.Entry<Long, Double>> topK = similarities.entrySet().stream()
                .sorted((a, b) -> Double.compare(b.getValue(), a.getValue()))
                .limit(K)
                .collect(Collectors.toList());

        // 加权聚合
        Map<Long, Double> scores = new HashMap<>();
        double simSum = topK.stream().mapToDouble(Map.Entry::getValue).sum();

        for (Map.Entry<Long, Double> neighbor : topK) {
            Long neighborId = neighbor.getKey();
            double sim = neighbor.getValue();
            Map<Long, Double> neighborRatings = matrix.get(neighborId);

            for (Map.Entry<Long, Double> entry : neighborRatings.entrySet()) {
                Long bookId = entry.getKey();
                if (targetRatings.containsKey(bookId)) continue;
                scores.merge(bookId, entry.getValue() * sim / simSum, Double::sum);
            }
        }

        return scores.entrySet().stream()
                .sorted((a, b) -> Double.compare(b.getValue(), a.getValue()))
                .limit(topN)
                .map(e -> new ScoredBook(e.getKey(), e.getValue()))
                .collect(Collectors.toList());

    }

    @Override
    public String name() {
        return "UserCF";
    }

    private Map<Long, Map<Long, Double>> buildMatrix(List<Rating> ratings) {
        Map<Long, Map<Long, Double>> matrix = new HashMap<>();
        for (Rating r : ratings) {
            matrix.computeIfAbsent(r.getUserId(), k -> new HashMap<>())
                    .put(r.getBookId(), r.getScore().doubleValue());
        }
        return matrix;
    }

    private double cosineSimilarity(Map<Long, Double> v1, Map<Long, Double> v2) {
        Set<Long> common = new HashSet<>(v1.keySet());
        common.retainAll(v2.keySet());
        if (common.size() < 3) return 0;
        double dot = 0, norm1 = 0, norm2 = 0;
        for (Long bookId : common) {
            double s1 = v1.get(bookId);
            double s2 = v2.get(bookId);
            dot += s1 * s2;
            norm1 += s1 * s1;
            norm2 += s2 * s2;
        }
        return norm1 > 0 && norm2 > 0 ? dot / (Math.sqrt(norm1) * Math.sqrt(norm2)) : 0;
    }

}
