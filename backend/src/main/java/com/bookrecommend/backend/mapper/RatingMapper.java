package com.bookrecommend.backend.mapper;

import com.bookrecommend.backend.entity.Rating;
import org.apache.ibatis.annotations.Mapper;

import java.util.List;

@Mapper
public interface RatingMapper {

    /**
     * 插入评分
     */
    int insert(Rating rating);

    /**
     * 更新评分
     */
    int update(Rating rating);

    /**
     * 查询某个用户的所有评分
     */
    List<Rating> findByUserId(Long userId);

    /**
     * 查询某本书的所有评分
     */
    List<Rating> findByBookId(Long bookId);

    /**
     * 查询全部评分（用于构建用户-物品矩阵）
     */
    List<Rating> findAll();

    /**
     * 查询指定用户的评分（用于快速路径：只加载邻居的评分）
     */
    List<Rating> findByUserIds(List<Long> userIds);

    /**
     * 查询某个用户对某本书的已有评分
     */
    Rating findByUserIdAndBookId(Long userId, Long bookId);

}
