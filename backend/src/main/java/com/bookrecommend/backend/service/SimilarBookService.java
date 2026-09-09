package com.bookrecommend.backend.service;

import com.bookrecommend.backend.entity.Book;
import com.bookrecommend.backend.mapper.BookMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.concurrent.TimeUnit;

/**
 * 相似图书服务
 * 策略：同分类 > 同作者 > 均分×评分人数
 * 在稀疏数据集上比纯协同过滤更可靠
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class SimilarBookService {

    private final BookMapper bookMapper;
    private final RedisTemplate<String, Object> redisTemplate;

    private static final String REDIS_PREFIX = "brs:similar:";
    private static final long TTL_HOURS = 6;

    @SuppressWarnings("unchecked")
    public List<Book> getSimilarBooks(Long bookId, int topN) {

        String key = REDIS_PREFIX + bookId;

        // 查缓存
        List<Integer> cachedIds = (List<Integer>) redisTemplate.opsForValue().get(key);
        if (cachedIds != null && !cachedIds.isEmpty()) {
            List<Book> result = new ArrayList<>();
            for (Integer id : cachedIds) {
                Book book = bookMapper.findById(id.longValue());
                if (book != null && result.size() < topN) {
                    result.add(book);
                }
            }
            if (!result.isEmpty()) return result;
        }

        // 计算并缓存
        return computeAndCache(bookId, topN);

    }

    private List<Book> computeAndCache(Long targetBookId, int topN) {

        Book target = bookMapper.findById(targetBookId);
        if (target == null) return Collections.emptyList();

        String category = target.getCategory();
        String author = target.getAuthor();
        log.info("SimilarBookService: targetId={}, category={}, author={}", targetBookId, category, author);

        // 获取所有图书 + 打分
        List<Book> allBooks = bookMapper.findAllSimple();
        Map<Long, Integer> scoreMap = new HashMap<>();
        List<Book> candidates = new ArrayList<>();

        for (Book b : allBooks) {
            if (b.getId().equals(targetBookId)) continue;

            int score = 0;
            if (category != null && category.equals(b.getCategory())) score += 100;
            if (author != null && author.equals(b.getAuthor())) score += 50;
            int cnt = b.getRatingCount() != null ? b.getRatingCount() : 0;
            score += Math.min(cnt, 20);

            if (score > 0) {
                scoreMap.put(b.getId(), score);
                candidates.add(b);
            }
        }

        candidates.sort((a, b) -> {
            int sa = scoreMap.getOrDefault(a.getId(), 0);
            int sb = scoreMap.getOrDefault(b.getId(), 0);
            if (sa != sb) return Integer.compare(sb, sa);
            // 平分时按均分降序
            double aa = a.getAvgRating() != null ? a.getAvgRating() : 0;
            double ba = b.getAvgRating() != null ? b.getAvgRating() : 0;
            return Double.compare(ba, aa);
        });

        long sameCatCount = candidates.stream()
                .filter(b -> category != null && category.equals(b.getCategory()))
                .count();
        log.info("SimilarBookService: {} candidates, {} same-category", candidates.size(), sameCatCount);

        // 取 Top-N
        List<Book> result = new ArrayList<>();
        List<Integer> cacheIds = new ArrayList<>();
        for (int i = 0; i < Math.min(candidates.size(), Math.max(topN, 8)); i++) {
            Book b = candidates.get(i);
            if (result.size() < topN) result.add(b);
            if (cacheIds.size() < 8) cacheIds.add(b.getId().intValue());
        }

        // 缓存
        if (!cacheIds.isEmpty()) {
            redisTemplate.opsForValue().set(
                    REDIS_PREFIX + targetBookId,
                    cacheIds,
                    TTL_HOURS,
                    TimeUnit.HOURS
            );
        }

        return result;

    }

}
