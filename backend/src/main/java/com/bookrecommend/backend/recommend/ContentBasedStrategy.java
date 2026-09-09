package com.bookrecommend.backend.recommend;

import com.bookrecommend.backend.entity.Book;
import com.bookrecommend.backend.entity.Rating;
import com.bookrecommend.backend.mapper.BookMapper;
import com.bookrecommend.backend.mapper.RatingMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.stream.Collectors;

/**
 * ContentBased: 基于内容的推荐（用户画像匹配）
 *
 * 原理：
 * 1. 从用户的评分历史构建兴趣画像（分类50% + 作者35% + 出版社15%）
 *    - 喜欢哪些分类（高分书的分类权重高）
 *    - 喜欢哪些作者（高分书的作者权重高）
 *    - 喜欢哪些出版社（高分书的出版社权重高）
 * 2. 对所有未读图书，计算与用户画像的匹配度
 * 3. 返回匹配度最高的 Top-N
 */
@Component
@RequiredArgsConstructor
public class ContentBasedStrategy implements RecommendStrategy {

    private final RatingMapper ratingMapper;
    private final BookMapper bookMapper;

    // 内存缓存：全量图书列表（不变数据）
    private volatile List<Book> cachedAllBooks;

    @Override
    public List<ScoredBook> recommend(Long userId, int topN) {

        // 1. 获取用户所有评分
        List<Rating> userRatings = ratingMapper.findByUserId(userId);
        if (userRatings.isEmpty()) return Collections.emptyList();

        // 2. 获取所有图书（内存缓存，避免重复查 MySQL）
        if (cachedAllBooks == null) {
            synchronized (this) {
                if (cachedAllBooks == null) {
                    cachedAllBooks = bookMapper.findAllSimple();
                }
            }
        }
        List<Book> allBooks = cachedAllBooks;

        // 3. 获取用户已评图书的完整信息
        Set<Long> ratedBookIds = userRatings.stream()
                .map(Rating::getBookId).collect(Collectors.toSet());

        Map<Long, Book> bookMap = new HashMap<>();
        for (Book b : allBooks) {
            bookMap.put(b.getId(), b);
        }

        // 4. 构建用户画像（分类 + 作者 + 出版社）
        Map<String, Double> categoryWeights = new HashMap<>();   // 分类 -> 权重
        Map<String, Double> authorWeights = new HashMap<>();     // 作者 -> 权重
        Map<String, Double> publisherWeights = new HashMap<>();  // 出版社 -> 权重

        for (Rating r : userRatings) {
            Book book = bookMap.get(r.getBookId());
            if (book == null) continue;

            double weight = r.getScore() / 10.0; // 归一化到 0~1

            String category = book.getCategory();
            if (category != null && !category.isEmpty()) {
                categoryWeights.merge(category, weight, Double::sum);
            }
            String author = book.getAuthor();
            if (author != null && !author.isEmpty()) {
                authorWeights.merge(author, weight, Double::sum);
            }
            String publisher = book.getPublisher();
            if (publisher != null && !publisher.isEmpty()) {
                publisherWeights.merge(publisher, weight, Double::sum);
            }
        }

        // 5. 对未读图书打分（只检查用户偏好分类下的书，大幅剪枝）
        final double CAT_RATIO = 0.50;
        final double AUTHOR_RATIO = 0.35;
        final double PUBLISHER_RATIO = 0.15;

        double catMax = categoryWeights.values().stream().max(Double::compareTo).orElse(1.0);
        double authorMax = authorWeights.values().stream().max(Double::compareTo).orElse(1.0);
        double pubMax = publisherWeights.values().stream().max(Double::compareTo).orElse(1.0);

        // 按分类分组，偏好分类优先
        Set<String> preferredCats = categoryWeights.keySet();
        List<Book> priorityBooks = new ArrayList<>();
        List<Book> otherBooks = new ArrayList<>();

        for (Book book : allBooks) {
            if (ratedBookIds.contains(book.getId())) continue;
            if (book.getCategory() != null && preferredCats.contains(book.getCategory())) {
                priorityBooks.add(book);
            } else {
                otherBooks.add(book);
            }
        }

        // 先给偏好分类的书打分
        List<ScoredBook> results = new ArrayList<>();
        scoreBooks(priorityBooks, ratedBookIds, categoryWeights, authorWeights, publisherWeights,
                catMax, authorMax, pubMax, CAT_RATIO, AUTHOR_RATIO, PUBLISHER_RATIO, results);

        // 偏好分类不够 topN × 2，再扩大范围
        if (results.size() < topN * 2) {
            scoreBooks(otherBooks, ratedBookIds, categoryWeights, authorWeights, publisherWeights,
                    catMax, authorMax, pubMax, CAT_RATIO, AUTHOR_RATIO, PUBLISHER_RATIO, results);
        }

        // 6. 排序返回 Top-N
        results.sort((a, b) -> Double.compare(b.getScore(), a.getScore()));
        if (results.size() > topN) {
            results = results.subList(0, topN);
        }
        return results;

    }

    private void scoreBooks(List<Book> books, Set<Long> ratedBookIds,
            Map<String, Double> categoryWeights, Map<String, Double> authorWeights,
            Map<String, Double> publisherWeights,
            double catMax, double authorMax, double pubMax,
            double catRatio, double authorRatio, double pubRatio,
            List<ScoredBook> results) {

        for (Book book : books) {
            double categoryScore = 0, authorScore = 0, publisherScore = 0;

            String category = book.getCategory();
            if (category != null && categoryWeights.containsKey(category)) {
                categoryScore = categoryWeights.get(category) / catMax;
            }

            String author = book.getAuthor();
            if (author != null && authorWeights.containsKey(author)) {
                authorScore = authorWeights.get(author) / authorMax;
            }

            String publisher = book.getPublisher();
            if (publisher != null && publisherWeights.containsKey(publisher)) {
                publisherScore = publisherWeights.get(publisher) / pubMax;
            }

            double totalScore = catRatio * categoryScore
                    + authorRatio * authorScore
                    + pubRatio * publisherScore;
            if (totalScore > 0) {
                results.add(new ScoredBook(book.getId(), totalScore));
            }
        }

    }

    @Override
    public String name() {
        return "ContentBased";
    }

}
