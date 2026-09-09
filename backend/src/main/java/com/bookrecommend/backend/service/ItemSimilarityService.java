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
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 物品相似度预计算服务
 * 离线计算每本书的 Top-20 相似书，存 Redis
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ItemSimilarityService {

    private final RatingMapper ratingMapper;
    private final RedisTemplate<String, Object> redisTemplate;

    private static final String PREFIX = "brs:sim:item:";
    private static final int TOP_K = 20;
    private static final long TTL_HOURS = 36;

    @PostConstruct
    public void init() {
        new Thread(this::buildAll, "item-sim-builder").start();
    }

    @Scheduled(cron = "0 0 3 * * ?")
    public void scheduledBuild() {
        buildAll();
    }

    /**
     * 获取某本书的相似书（在线查询）
     */
    @SuppressWarnings("unchecked")
    public Map<Long, Double> getSimilarItems(Long bookId) {
        String key = PREFIX + bookId;
        Map<Object, Object> raw = redisTemplate.opsForHash().entries(key);
        if (raw != null && !raw.isEmpty()) {
            Map<Long, Double> result = new HashMap<>();
            for (Map.Entry<Object, Object> e : raw.entrySet()) {
                result.put(Long.valueOf(e.getKey().toString()),
                        Double.valueOf(e.getValue().toString()));
            }
            return result;
        }
        return null;
    }

    private void buildAll() {
        long start = System.currentTimeMillis();
        log.info("开始构建物品相似度...");

        List<Rating> allRatings = ratingMapper.findAll();

        // book→(user,score) + user→[books]（倒排索引）
        Map<Long, Map<Long, Double>> itemMatrix = new HashMap<>();
        Map<Long, List<Long>> userToBooks = new HashMap<>();

        for (Rating r : allRatings) {
            itemMatrix.computeIfAbsent(r.getBookId(), k -> new HashMap<>())
                    .put(r.getUserId(), r.getScore().doubleValue());
            userToBooks.computeIfAbsent(r.getUserId(), k -> new ArrayList<>())
                    .add(r.getBookId());
        }

        List<Long> bookIds = new ArrayList<>(itemMatrix.keySet());
        log.info("{} 本书待计算", bookIds.size());

        AtomicInteger done = new AtomicInteger(0);
        bookIds.parallelStream().forEach(bookId -> {
            Map<Long, Double> vec = itemMatrix.get(bookId);
            if (vec == null || vec.size() < 2) {
                done.incrementAndGet();
                return;
            }

            // 倒排索引：只比较有共同评分者的书
            Set<Long> candidates = new HashSet<>();
            for (Long uid : vec.keySet()) {
                List<Long> books = userToBooks.get(uid);
                if (books != null) candidates.addAll(books);
            }
            candidates.remove(bookId);

            Map<Long, Double> sims = new HashMap<>();
            for (Long otherId : candidates) {
                Map<Long, Double> otherVec = itemMatrix.get(otherId);
                if (otherVec == null) continue;
                double sim = cosineSimilarity(vec, otherVec);
                if (sim > 0) sims.put(otherId, sim);
            }

            storeNeighbors(bookId, sims);
            int d = done.incrementAndGet();
            if (d % 2000 == 0) log.info("物品相似度: {}/{}", d, bookIds.size());
        });

        long elapsed = (System.currentTimeMillis() - start) / 1000;
        log.info("物品相似度构建完成，耗时 {}s", elapsed);
    }

    private void storeNeighbors(Long bookId, Map<Long, Double> sims) {
        List<Map.Entry<Long, Double>> topList = new ArrayList<>(sims.entrySet());
        topList.sort((a, b) -> Double.compare(b.getValue(), a.getValue()));

        Map<String, String> hash = new LinkedHashMap<>();
        for (int i = 0; i < Math.min(TOP_K, topList.size()); i++) {
            Map.Entry<Long, Double> e = topList.get(i);
            hash.put(e.getKey().toString(), e.getValue().toString());
        }

        if (!hash.isEmpty()) {
            String key = PREFIX + bookId;
            redisTemplate.opsForHash().putAll(key, hash);
            redisTemplate.expire(key, TTL_HOURS, TimeUnit.HOURS);
        }
    }

    private double cosineSimilarity(Map<Long, Double> v1, Map<Long, Double> v2) {
        Set<Long> common = new HashSet<>(v1.keySet());
        common.retainAll(v2.keySet());
        if (common.size() < 2) return 0;
        double dot = 0, n1 = 0, n2 = 0;
        for (Long uid : common) {
            double s1 = v1.get(uid), s2 = v2.get(uid);
            dot += s1 * s2;
            n1 += s1 * s1;
            n2 += s2 * s2;
        }
        return n1 > 0 && n2 > 0 ? dot / (Math.sqrt(n1) * Math.sqrt(n2)) : 0;
    }

}
