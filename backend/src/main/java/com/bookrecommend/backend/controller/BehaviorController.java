package com.bookrecommend.backend.controller;

import com.bookrecommend.backend.entity.Behavior;
import com.bookrecommend.backend.mapper.BehaviorMapper;
import com.bookrecommend.backend.mapper.SysUserMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 行为埋点：曝光 / 点击 / 评分
 * 数据写入 behavior 表，支撑 AB 实验的 CTR 统计（userId % 2 分桶）
 */
@RestController
@RequestMapping("/behavior")
@RequiredArgsConstructor
public class BehaviorController {

    private final BehaviorMapper behaviorMapper;
    private final SysUserMapper sysUserMapper;

    /**
     * 上报行为: {bookId, type}，type 取值 exposure / click / rating
     */
    @PostMapping("/report")
    public Map<String, Object> report(@RequestBody Map<String, Object> body) {
        String username = SecurityContextHolder.getContext()
                .getAuthentication().getName();
        Long userId = sysUserMapper.findIdByUsername(username);

        Long bookId = Long.valueOf(String.valueOf(body.get("bookId")));
        String type = String.valueOf(body.get("type"));
        if (!"exposure".equals(type) && !"click".equals(type) && !"rating".equals(type)) {
            return Map.of("code", 400, "message", "type 非法");
        }

        Behavior b = new Behavior();
        b.setUserId(userId);
        b.setBookId(bookId);
        b.setType(type);
        behaviorMapper.insert(b);

        return Map.of("code", 200);
    }

    /**
     * AB 实验分组统计：返回各分桶的曝光/点击/CTR
     */
    @GetMapping("/ab-stats")
    public Map<String, Object> abStats() {
        return Map.of("code", 200, "data", behaviorMapper.ctrByBucket(),
                "note", "bucket=0 -> A组(混合加权), bucket=1 -> B组(双塔+DeepFM)");
    }
}
