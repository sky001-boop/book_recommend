package com.bookrecommend.backend.controller;

import com.bookrecommend.backend.dto.RatingRequest;
import com.bookrecommend.backend.entity.Rating;
import com.bookrecommend.backend.mapper.SysUserMapper;
import com.bookrecommend.backend.service.RatingService;
import com.bookrecommend.backend.service.UserSimilarityService;
import lombok.RequiredArgsConstructor;
import org.springframework.cache.CacheManager;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.Objects;

@RestController
@RequestMapping("/rating")
@RequiredArgsConstructor
public class RatingController {

    private final RatingService ratingService;
    private final SysUserMapper sysUserMapper;
    private final CacheManager cacheManager;
    private final UserSimilarityService similarityService;

    /**
     * 提交评分
     */
    @PostMapping("/submit")
    public Map<String, Object> submit(@RequestBody RatingRequest request) {

        String username = SecurityContextHolder.getContext()
                .getAuthentication().getName();

        Long userId = sysUserMapper.findIdByUsername(username);

        Rating rating = ratingService.rateBook(userId, request.getBookId(), request.getScore());

        // 清除推荐缓存 + 增量更新邻居相似度（异步）
        Objects.requireNonNull(cacheManager.getCache("recommendations"))
                .evict(userId);
        new Thread(() -> similarityService.updateOne(userId)).start();

        return Map.of(
                "code", 200,
                "message", "评分成功",
                "data", rating
        );

    }

    /**
     * 当前用户的评分记录
     */
    @GetMapping("/my")
    public Map<String, Object> myRatings() {

        String username = SecurityContextHolder.getContext()
                .getAuthentication().getName();

        Long userId = sysUserMapper.findIdByUsername(username);

        List<Rating> ratings = ratingService.getUserRatings(userId);

        return Map.of(
                "code", 200,
                "data", ratings
        );

    }

}
