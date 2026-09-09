package com.bookrecommend.backend.controller;

import com.bookrecommend.backend.entity.Book;
import com.bookrecommend.backend.llm.RecommendReasonService;
import com.bookrecommend.backend.mapper.BookMapper;
import com.bookrecommend.backend.mapper.SysUserMapper;
import com.bookrecommend.backend.recommend.DeepRecommendService;
import com.bookrecommend.backend.recommend.HybridRecommendService;
import com.bookrecommend.backend.recommend.PopularityStrategy;
import com.bookrecommend.backend.recommend.RecommendItem;
import com.bookrecommend.backend.recommend.ScoredBook;
import lombok.RequiredArgsConstructor;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/recommend")
@RequiredArgsConstructor
public class RecommendController {

    private final HybridRecommendService hybridService;
    private final DeepRecommendService deepRecommendService;
    private final RecommendReasonService recommendReasonService;
    private final PopularityStrategy popularityStrategy;
    private final SysUserMapper sysUserMapper;
    private final BookMapper bookMapper;

    /**
     * 猜你喜欢 — 个性化推荐
     */
    @GetMapping("/my")
    public Map<String, Object> myRecommend(
            @RequestParam(defaultValue = "20") int topN
    ) {
        String username = SecurityContextHolder.getContext()
                .getAuthentication().getName();
        Long userId = sysUserMapper.findIdByUsername(username);

        List<RecommendItem> items = hybridService.recommend(userId, topN);

        return Map.of("code", 200, "data", items);
    }

    /**
     * 猜你喜欢 v2 — 双塔语义召回 + DeepFM 精排（模型服务不可用时降级为混合加权）
     */
    @GetMapping("/v2")
    public Map<String, Object> recommendV2(
            @RequestParam(defaultValue = "20") int topN
    ) {
        String username = SecurityContextHolder.getContext()
                .getAuthentication().getName();
        Long userId = sysUserMapper.findIdByUsername(username);

        List<RecommendItem> items = deepRecommendService.recommend(userId, topN);

        return Map.of("code", 200, "data", items);
    }

    /**
     * AB 实验推荐：userId % 2 = 0 走 A 组（混合加权），= 1 走 B 组（双塔+DeepFM）
     * 响应携带 group 字段，前端据此埋点曝光/点击
     */
    @GetMapping("/ab")
    public Map<String, Object> abRecommend(
            @RequestParam(defaultValue = "20") int topN
    ) {
        String username = SecurityContextHolder.getContext()
                .getAuthentication().getName();
        Long userId = sysUserMapper.findIdByUsername(username);

        boolean isGroupB = userId % 2 == 1;
        List<RecommendItem> items = isGroupB
                ? deepRecommendService.recommend(userId, topN)
                : hybridService.recommend(userId, topN);

        return Map.of("code", 200, "data", items,
                "group", isGroupB ? "B" : "A",
                "strategy", isGroupB ? "双塔召回+DeepFM精排" : "多路召回+混合加权");
    }

    /**
     * 猜你喜欢 v2 的个性化推荐理由（LLM 生成，未配置 Key 时为空）
     */
    @GetMapping("/v2/explain")
    public Map<String, Object> explainV2(
            @RequestParam(defaultValue = "10") int topN
    ) {
        String username = SecurityContextHolder.getContext()
                .getAuthentication().getName();
        Long userId = sysUserMapper.findIdByUsername(username);

        List<RecommendItem> items = deepRecommendService.recommend(userId, topN);
        Map<Long, String> reasons = recommendReasonService.generateReasons(userId, items);

        return Map.of("code", 200, "data", items, "reasons", reasons);
    }

    /**
     * 热门推荐 — 根据当前用户排除已评分的书
     */
    @GetMapping("/hot")
    public Map<String, Object> hot(
            @RequestParam(defaultValue = "20") int topN,
            @RequestParam(defaultValue = "0") int offset
    ) {

        String username = SecurityContextHolder.getContext()
                .getAuthentication().getName();
        Long userId = sysUserMapper.findIdByUsername(username);

        List<ScoredBook> hotBooks = popularityStrategy.recommend(userId, topN + offset);
        // 跳过前 offset 本，超出范围则回到开头
        if (offset > 0) {
            if (hotBooks.size() > offset) {
                hotBooks = hotBooks.subList(offset, Math.min(hotBooks.size(), offset + topN));
            } else {
                hotBooks = hotBooks.subList(0, Math.min(topN, hotBooks.size()));
            }
        }

        List<RecommendItem> items = new java.util.ArrayList<>();
        for (ScoredBook sb : hotBooks) {
            Book book = bookMapper.findById(sb.getBookId());
            if (book != null) {
                items.add(new RecommendItem(book, sb.getScore()));
            }
        }

        return Map.of("code", 200, "data", items);
    }

    /**
     * 手动刷新推荐缓存
     */
    @PostMapping("/refresh")
    @CacheEvict(value = "recommendations", allEntries = true)
    public Map<String, Object> refresh() {
        popularityStrategy.refreshCache();
        return Map.of("code", 200, "message", "缓存已刷新");
    }

    /**
     * 定时任务：每天凌晨 3 点重建热门缓存
     */
    @Scheduled(cron = "0 0 3 * * ?")
    public void scheduledRefresh() {
        popularityStrategy.refreshCache();
    }

}
