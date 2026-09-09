package com.bookrecommend.backend.entity;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class Book {

    private Long id;

    private String title;

    private String author;

    private String category;

    private String publisher;

    private String isbn;

    private Integer publishYear;

    private String description;

    private String cover;

    private LocalDateTime createTime;

    // === 以下字段来自聚合查询，不持久化 ===
    private Double avgRating;   // 社区平均分

    private Integer ratingCount; // 评分人数

}
