package com.bookrecommend.backend.service;

import com.bookrecommend.backend.entity.Rating;
import com.bookrecommend.backend.mapper.RatingMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import jakarta.annotation.PostConstruct;
import java.util.*;
import java.util.concurrent.TimeUnit;

/**
 * 用户相似度预计算服务
 * 离线计算所有用户的 Top-100 邻居，存 Redis
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class UserSimilarityService {

    private final RatingMapper ratingMapper;
    private final RedisTemplate<String, Object> redisTemplate;

    private static final String PREFIX = "brs:sim:user:";
    private static final int TOP_K = 100;
    private static final long TTL_HOURS = 36;

    /**
     * 应用启动 30 秒后异步构建全量用户相似度
     */
    @PostConstruct
    public void init() {
        new Thread(this::buildAll, "user-sim-builder").start();
    }

    /**
     * 凌晨 3 点定时重建
     */
    @Scheduled(cron = "0 0 3 * * ?")
    public void scheduledBuild() {
        buildAll();
    }

    /**
     * 获取某用户的邻居（在线查询）
     */
    @SuppressWarnings("unchecked")
    public Map<Long, Double> getNeighbors(Long userId) {
        String key = PREFIX + userId;
        Map<Object, Object> raw = redisTemplate.opsForHash().entries(key);
        if (raw != null && !raw.isEmpty()) {
            Map<Long, Double> neighbors = new HashMap<>();
            for (Map.Entry<Object, Object> e : raw.entrySet()) {
                neighbors.put(Long.valueOf(e.getKey().toString()),
                             Double.valueOf(e.getValue().toString()));
            }
            return neighbors;
        }
        return null;
    }

    /**
     * 增量更新：某个用户评分后，只重算他与其他人的相似度
     */
    public void updateOne(Long userId) {
        List<Rating> allRatings = ratingMapper.findAll();
        Map<Long, Map<Long, Double>> matrix = buildMatrix(allRatings);
        Map<Long, Double> targetVec = matrix.get(userId);
        if (targetVec == null) return;

        Map<Long, Double> similarities = new HashMap<>();
        for (Map.Entry<Long, Map<Long, Double>> entry : matrix.entrySet()) {
            Long otherId = entry.getKey();
            if (otherId.equals(userId)) continue;
            double sim = cosineSimilarity(targetVec, entry.getValue());
            if (sim > 0) similarities.put(otherId, sim);
        }

        storeNeighbors(userId, similarities);
    }

    /**
     * 全量构建（多线程并行）
     */
    private void buildAll() {
        long start = System.currentTimeMillis();
        log.info("开始构建用户相似度矩阵...");

        List<Rating> allRatings = ratingMapper.findAll();
        Map<Long, Map<Long, Double>> matrix = buildMatrix(allRatings);
        List<Long> userIds = new ArrayList<>(matrix.keySet());

        log.info("矩阵构建完成，{} 个用户，多线程并行计算相似度", userIds.size());

        // 并行计算
        java.util.concurrent.atomic.AtomicInteger done = new java.util.concurrent.atomic.AtomicInteger(0);
        int total = userIds.size();

        userIds.parallelStream().forEach(uid -> {
            Map<Long, Double> vec = matrix.get(uid);
            Map<Long, Double> sims = Collections.synchronizedMap(new HashMap<>());
            for (Long other : userIds) {
                if (other.equals(uid)) continue;
                double sim = cosineSimilarity(vec, matrix.get(other));
                if (sim > 0.05) sims.put(other, sim);
            }
            storeNeighbors(uid, sims);
            int d = done.incrementAndGet();
            if (d % 1000 == 0) log.info("进度: {}/{}", d, total);
        });

        long elapsed = (System.currentTimeMillis() - start) / 1000;
        log.info("用户相似度构建完成，耗时 {}s", elapsed);
    }

    private void storeNeighbors(Long userId, Map<Long, Double> sims) {
        // 排序取 Top-K
        List<Map.Entry<Long, Double>> topList = new ArrayList<>(sims.entrySet());
        topList.sort((a, b) -> Double.compare(b.getValue(), a.getValue()));

        Map<String, String> hash = new LinkedHashMap<>();
        for (int i = 0; i < Math.min(TOP_K, topList.size()); i++) {
            Map.Entry<Long, Double> e = topList.get(i);
            hash.put(e.getKey().toString(), e.getValue().toString());
        }

        if (!hash.isEmpty()) {
            String key = PREFIX + userId;
            redisTemplate.opsForHash().putAll(key, hash);
            redisTemplate.expire(key, TTL_HOURS, TimeUnit.HOURS);
        }
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
        if (common.size() < 2) return 0;
        double dot = 0, n1 = 0, n2 = 0;
        for (Long id : common) {
            double s1 = v1.get(id), s2 = v2.get(id);
            dot += s1 * s2;
            n1 += s1 * s1;
            n2 += s2 * s2;
        }
        return n1 > 0 && n2 > 0 ? dot / (Math.sqrt(n1) * Math.sqrt(n2)) : 0;
    }

}
