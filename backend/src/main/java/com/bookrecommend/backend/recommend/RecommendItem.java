package com.bookrecommend.backend.recommend;

import com.bookrecommend.backend.entity.Book;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 推荐结果——包含图书信息和推荐分
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class RecommendItem {

    private Long id;

    private String title;

    private String author;

    private String publisher;

    private String category;

    private String cover;

    private Double avgRating;

    private Integer ratingCount;

    private Double recommendScore;

    public RecommendItem(Book book, Double recommendScore) {
        this.id = book.getId();
        this.title = book.getTitle();
        this.author = book.getAuthor();
        this.category = book.getCategory();
        this.publisher = book.getPublisher();
        this.cover = book.getCover();
        this.avgRating = book.getAvgRating();
        this.ratingCount = book.getRatingCount();
        this.recommendScore = recommendScore;
    }

}
