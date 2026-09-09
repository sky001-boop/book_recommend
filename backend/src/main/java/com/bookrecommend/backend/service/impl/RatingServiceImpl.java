package com.bookrecommend.backend.service.impl;

import com.bookrecommend.backend.entity.Rating;
import com.bookrecommend.backend.exception.BusinessException;
import com.bookrecommend.backend.mapper.RatingMapper;
import com.bookrecommend.backend.service.RatingService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class RatingServiceImpl implements RatingService {

    private final RatingMapper ratingMapper;

    @Override
    public Rating rateBook(Long userId, Long bookId, Float score) {

        // 分数范围校验 (Book-Crossing 数据集使用 1-10 分制)
        if (score == null || score < 1 || score > 10) {
            throw new BusinessException(400, "评分必须在 1 - 10 之间");
        }

        // 检查是否已有评分
        Rating existing = ratingMapper.findByUserIdAndBookId(userId, bookId);
        if (existing != null) {
            // 更新已有评分
            existing.setScore(score);
            ratingMapper.update(existing);
            return existing;
        }

        // 新增评分
        Rating rating = new Rating();
        rating.setUserId(userId);
        rating.setBookId(bookId);
        rating.setScore(score);
        ratingMapper.insert(rating);
        return rating;

    }

    @Override
    public List<Rating> getUserRatings(Long userId) {
        return ratingMapper.findByUserId(userId);
    }

}
