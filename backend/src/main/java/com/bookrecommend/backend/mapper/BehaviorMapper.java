package com.bookrecommend.backend.mapper;

import com.bookrecommend.backend.entity.Behavior;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;
import java.util.Map;

/**
 * 行为埋点（曝光/点击），支撑 AB 实验效果统计
 */
@Mapper
public interface BehaviorMapper {

    int insert(Behavior behavior);

    /**
     * 按分组统计 CTR：userId % 2 = bucket（0 -> A 组，1 -> B 组）
     * 返回 [{bucket, exposures, clicks}]
     */
    List<Map<String, Object>> ctrByBucket();
}
