package com.bookrecommend.backend.service;

import com.bookrecommend.backend.entity.Rating;

import java.util.List;

public interface RatingService {

    /**
     * 提交或更新评分
     */
    Rating rateBook(Long userId, Long bookId, Float score);

    /**
     * 获取用户的所有评分记录
     */
    List<Rating> getUserRatings(Long userId);

}
