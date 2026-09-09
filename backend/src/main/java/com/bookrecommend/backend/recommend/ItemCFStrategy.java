package com.bookrecommend.backend.recommend;

import com.bookrecommend.backend.entity.Rating;
import com.bookrecommend.backend.mapper.RatingMapper;
import com.bookrecommend.backend.service.ItemSimilarityService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.stream.Collectors;

/**
 * ItemCF: 基于物品的协同过滤（物品相似度预计算版）
 *
 * 只加载当前用户评分（不拉全量），相似度从 Redis 读
 */
@Component
@RequiredArgsConstructor
public class ItemCFStrategy implements RecommendStrategy {

    private final RatingMapper ratingMapper;
    private final ItemSimilarityService similarityService;

    @Override
    public List<ScoredBook> recommend(Long userId, int topN) {

        // 只加载当前用户的评分
        List<Rating> userRatings = ratingMapper.findByUserId(userId);
        if (userRatings.isEmpty()) return Collections.emptyList();

        // 高分书（≥7分）
        Map<Long, Double> ratedBooks = new HashMap<>();
        List<Long> favoriteBooks = new ArrayList<>();

        for (Rating r : userRatings) {
            ratedBooks.put(r.getBookId(), r.getScore().doubleValue());
            if (r.getScore() >= 7) {
                favoriteBooks.add(r.getBookId());
            }
        }

        // 从 Redis 读每本高分书的 Top-20 相似书
        Map<Long, Double> scores = new HashMap<>();

        for (Long bookId : favoriteBooks) {
            Map<Long, Double> similar = similarityService.getSimilarItems(bookId);
            if (similar == null) continue;

            double myRating = ratedBooks.get(bookId);
            for (Map.Entry<Long, Double> sim : similar.entrySet()) {
                Long candidateId = sim.getKey();
                if (ratedBooks.containsKey(candidateId)) continue;
                scores.merge(candidateId, sim.getValue() * myRating, Double::sum);
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
        return "ItemCF";
    }

}
