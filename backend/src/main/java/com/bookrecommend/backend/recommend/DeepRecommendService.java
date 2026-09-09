package com.bookrecommend.backend.recommend;

import com.bookrecommend.backend.entity.Book;
import com.bookrecommend.backend.mapper.BookMapper;
import com.bookrecommend.backend.model.ModelServiceClient;
import com.bookrecommend.backend.model.RankCandidate;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.stream.Collectors;

/**
 * 深度学习推荐链路（v2）：双塔语义召回 + DeepFM 精排
 *
 * 流程:
 *   1. 多路召回生成候选 + 通道策略分（HybridRecommendService）
 *   2. 双塔召回 Top-100 并入候选（模型服务 /embed）
 *   3. DeepFM 对候选精排打分（模型服务 /rank，输入含策略分特征）
 *   4. 任一步失败/超时 → 降级为现有混合加权（保证推荐可用性）
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class DeepRecommendService {

    private final HybridRecommendService hybridService;
    private final ModelServiceClient modelClient;
    private final BookMapper bookMapper;

    @Cacheable(value = "recommendations_v2", key = "#userId")
    public List<RecommendItem> recommend(Long userId, int topN) {

        List<RankCandidate> candidates = hybridService.recommendCandidates(userId, topN);
        if (candidates.isEmpty()) {
            return Collections.emptyList();
        }
        if (!modelClient.isEnabled()) {
            log.debug("模型服务未启用，走混合加权");
            return hybridService.recommend(userId, topN);
        }

        try {
            // 双塔召回并入候选（策略分未知 -> 0）
            List<Long> towerItems = modelClient.embed(userId);
            if (towerItems != null && !towerItems.isEmpty()) {
                Set<Long> known = candidates.stream()
                        .map(RankCandidate::bookId).collect(Collectors.toSet());
                for (Long bid : towerItems) {
                    if (!known.contains(bid)) {
                        candidates.add(new RankCandidate(bid, 0.0, 0.0, 0.0, 0.0));
                        known.add(bid);
                    }
                }
            }

            // DeepFM 精排
            Map<Long, Double> ranked = modelClient.rank(userId, candidates);
            List<Long> topIds = candidates.stream()
                    .sorted(Comparator.comparingDouble(
                            (RankCandidate c) -> ranked.getOrDefault(c.bookId(), 0.0)).reversed())
                    .limit(topN)
                    .map(RankCandidate::bookId)
                    .toList();

            List<RecommendItem> result = new ArrayList<>();
            for (Long id : topIds) {
                Book book = bookMapper.findById(id);
                if (book != null) {
                    result.add(new RecommendItem(book, ranked.getOrDefault(id, 0.0)));
                }
            }
            if (result.isEmpty()) {
                throw new IllegalStateException("精排结果为空");
            }
            return result;

        } catch (Exception e) {
            log.warn("模型服务调用失败，降级为混合加权: {}", e.getMessage());
            return hybridService.recommend(userId, topN);
        }
    }
}
