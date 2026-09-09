package com.bookrecommend.backend.entity;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class Rating {

    private Long id;

    private Long userId;

    private Long bookId;

    private Float score;

    private LocalDateTime createTime;

}
