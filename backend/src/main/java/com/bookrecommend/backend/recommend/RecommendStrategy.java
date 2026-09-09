package com.bookrecommend.backend.recommend;

import java.util.List;

/**
 * 推荐策略接口
 * 所有推荐算法实现此接口，体现多态
 */
public interface RecommendStrategy {

    /**
     * 为指定用户生成推荐
     *
     * @param userId 用户 ID
     * @param topN   返回 Top-N 推荐
     * @return 推荐图书 ID 列表（带推荐分数）
     */
    List<ScoredBook> recommend(Long userId, int topN);

    /**
     * 算法名称
     */
    String name();

}
