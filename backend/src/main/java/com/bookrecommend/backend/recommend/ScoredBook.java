package com.bookrecommend.backend.recommend;

import lombok.AllArgsConstructor;
import lombok.Data;

/**
 * 推荐结果——带分数的图书
 */
@Data
@AllArgsConstructor
public class ScoredBook {

    private Long bookId;

    private Double score;

}
