package com.bookrecommend.backend.recommend;

import com.bookrecommend.backend.entity.Book;
import com.bookrecommend.backend.mapper.BookMapper;
import com.bookrecommend.backend.mapper.RatingMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.concurrent.*;
import java.util.stream.Collectors;

/**
 * Hybrid 融合推荐服务
 *
 * 根据用户的评分行为特征，动态调整 4 个算法的权重
 * - 老用户(>50评)：信任协同过滤
 * - 中等用户(5-50评)：侧重内容画像
 * - 新用户(<5评)：侧重热门 + 内容
 * - 冷启动(0评)：纯热门
 */
@Service
@RequiredArgsConstructor
public class HybridRecommendService {

    private final UserCFStrategy userCF;
    private final ItemCFStrategy itemCF;
    private final ContentBasedStrategy contentBased;
    private final PopularityStrategy popularity;
    private final RatingMapper ratingMapper;
    private final BookMapper bookMapper;

    /**
     * 智能权重推荐
     */
    @Cacheable(value = "recommendations", key = "#userId")
    public List<RecommendItem> recommend(Long userId, int topN) {

        int ratingCount = ratingMapper.findByUserId(userId).size();
        if (ratingCount == 0) {
            return Collections.emptyList();
        }

        double[] weights = computeWeights(ratingCount);
        List<List<ScoredBook>> channels = computeChannelResults(userId, topN * 2, weights);

        // 加权合并
        Map<Long, Double> merged = new HashMap<>();
        mergeInto(merged, channels.get(0), weights[0]);
        mergeInto(merged, channels.get(1), weights[1]);
        mergeInto(merged, channels.get(2), weights[2]);
        mergeInto(merged, channels.get(3), weights[3]);

        // 排序取 Top-N
        List<Long> topIds = merged.entrySet().stream()
                .sorted((a, b) -> Double.compare(b.getValue(), a.getValue()))
                .limit(topN)
                .map(Map.Entry::getKey)
                .collect(Collectors.toList());

        // 只查 Top-N 本书的详细信息
        List<RecommendItem> result = new ArrayList<>();
        for (Long id : topIds) {
            Book book = bookMapper.findById(id);
            if (book != null) {
                result.add(new RecommendItem(book, merged.get(id)));
            }
        }

        return result;

    }

    /**
     * v2 候选生成：返回候选集及其归一化后的通道策略分
     * （策略分作为 DeepFM 精排模型的输入特征，由 DeepRecommendService 消费）
     */
    public List<com.bookrecommend.backend.model.RankCandidate> recommendCandidates(Long userId, int topN) {

        int ratingCount = ratingMapper.findByUserId(userId).size();
        if (ratingCount == 0) {
            return Collections.emptyList();
        }

        double[] weights = computeWeights(ratingCount);
        List<List<ScoredBook>> channels = computeChannelResults(userId, topN * 2, weights);

        // 候选 bookId -> [userCF, itemCF, content, popular] 归一化策略分
        Map<Long, double[]> scoreMap = new HashMap<>();
        for (int c = 0; c < 4; c++) {
            for (ScoredBook sb : channels.get(c)) {
                double[] s = scoreMap.computeIfAbsent(sb.getBookId(), k -> new double[4]);
                s[c] = sb.getScore();
            }
        }

        List<com.bookrecommend.backend.model.RankCandidate> result = new ArrayList<>();
        for (Map.Entry<Long, double[]> e : scoreMap.entrySet()) {
            double[] s = e.getValue();
            result.add(new com.bookrecommend.backend.model.RankCandidate(e.getKey(), s[0], s[1], s[2], s[3]));
        }
        return result;
    }

    /**
     * 4 路召回并行计算 + min-max 归一化
     * 返回顺序: [userCF, itemCF, content, popular]
     */
    private List<List<ScoredBook>> computeChannelResults(Long userId, int topN, double[] weights) {

        // 4 个算法并行计算（总耗时 = max(各算法耗时)，不再是 sum）
        ExecutorService executor = Executors.newFixedThreadPool(4);
        List<ScoredBook> userCFResult, itemCFResult, contentResult, popularResult;
        try {
            Future<List<ScoredBook>> cfFuture = executor.submit(() ->
                    weights[0] > 0 ? userCF.recommend(userId, topN) : Collections.emptyList());
            Future<List<ScoredBook>> icfFuture = executor.submit(() ->
                    weights[1] > 0 ? itemCF.recommend(userId, topN) : Collections.emptyList());
            Future<List<ScoredBook>> cbFuture = executor.submit(() ->
                    weights[2] > 0 ? contentBased.recommend(userId, topN) : Collections.emptyList());
            Future<List<ScoredBook>> popFuture = executor.submit(() ->
                    popularity.recommend(userId, topN));

            userCFResult = cfFuture.get(30, TimeUnit.SECONDS);
            itemCFResult = icfFuture.get(30, TimeUnit.SECONDS);
            contentResult = cbFuture.get(30, TimeUnit.SECONDS);
            popularResult = popFuture.get(30, TimeUnit.SECONDS);
        } catch (Exception e) {
            userCFResult = Collections.emptyList();
            itemCFResult = Collections.emptyList();
            contentResult = Collections.emptyList();
            popularResult = Collections.emptyList();
        } finally {
            executor.shutdown();
        }

        // 归一化各算法分数
        normalize(userCFResult);
        normalize(itemCFResult);
        normalize(contentResult);
        normalize(popularResult);

        return List.of(userCFResult, itemCFResult, contentResult, popularResult);
    }

    /**
     * 根据评分数量动态分配权重
     *
     * 返回: [userCFWeight, itemCFWeight, contentWeight, popularWeight]
     */
    private double[] computeWeights(int ratingCount) {

        if (ratingCount == 0) {
            // 冷启动：纯热门
            return new double[]{0.0, 0.0, 0.0, 1.0};
        } else if (ratingCount < 5) {
            // 新用户：热门为主 + 内容辅助
            return new double[]{0.0, 0.1, 0.4, 0.5};
        } else if (ratingCount <= 50) {
            // 中等用户：内容为主 + 协同辅助
            return new double[]{0.2, 0.2, 0.4, 0.2};
        } else {
            // 老用户：协同为主 + 内容辅助
            return new double[]{0.35, 0.30, 0.25, 0.10};
        }

    }

    /**
     * Min-Max 归一化，将各算法的分数映射到 [0, 1]
     */
    private void normalize(List<ScoredBook> list) {
        if (list.isEmpty()) return;
        double max = list.stream().mapToDouble(ScoredBook::getScore).max().orElse(1);
        double min = list.stream().mapToDouble(ScoredBook::getScore).min().orElse(0);
        double range = max - min;
        if (range == 0) range = 1;
        for (ScoredBook sb : list) {
            sb.setScore((sb.getScore() - min) / range);
        }
    }

    /**
     * 将算法结果加权并入合并结果集
     */
    private void mergeInto(Map<Long, Double> merged, List<ScoredBook> list, double weight) {
        for (ScoredBook sb : list) {
            merged.merge(sb.getBookId(), sb.getScore() * weight, Double::sum);
        }
    }

}
