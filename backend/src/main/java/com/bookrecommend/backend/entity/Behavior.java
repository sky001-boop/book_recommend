package com.bookrecommend.backend.entity;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 行为埋点：曝光 / 点击 / 评分
 */
@Data
public class Behavior {

    private Long id;

    private Long userId;

    private Long bookId;

    /** exposure / click / rating */
    private String type;

    private LocalDateTime createTime;

}
