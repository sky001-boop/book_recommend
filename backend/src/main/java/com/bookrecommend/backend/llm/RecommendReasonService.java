package com.bookrecommend.backend.llm;

import com.bookrecommend.backend.entity.Book;
import com.bookrecommend.backend.entity.Rating;
import com.bookrecommend.backend.mapper.BookMapper;
import com.bookrecommend.backend.mapper.RatingMapper;
import com.bookrecommend.backend.recommend.RecommendItem;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.stream.Collectors;

/**
 * LLM 个性化推荐理由生成
 *
 * 流程:
 *   1. 从用户高分书(>=7)构建兴趣画像（Top 分类/作者）
 *   2. 画像 + 推荐列表拼 Prompt，批量生成一句话理由
 *   3. 结果解析为 {bookId -> reason}
 * LLM 不可用（未配 Key / 超时 / 解析失败）时返回空 Map，前端隐藏理由区域。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RecommendReasonService {

    private static final String SYSTEM_PROMPT = """
            你是图书推荐系统的推荐解释助手。根据用户的历史阅读偏好，为每本推荐图书生成一句不超过 25 字的中文推荐理由。
            理由必须引用用户的偏好（喜欢的分类或作者），格式要求严格输出 JSON 数组：
            [{"bookId": <数字>, "reason": "<理由>"}]
            """;

    private final LlmClient llmClient;
    private final RatingMapper ratingMapper;
    private final BookMapper bookMapper;
    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * 为推荐列表生成理由，返回 bookId -> reason（LLM 不可用时为空 Map）
     */
    public Map<Long, String> generateReasons(Long userId, List<RecommendItem> items) {
        if (items == null || items.isEmpty() || !llmClient.isEnabled()) {
            return Collections.emptyMap();
        }
        try {
            String profile = buildProfile(userId);
            String bookList = items.stream()
                    .limit(10)
                    .map(it -> it.getId() + ". 《" + it.getTitle() + "》 - " + it.getAuthor() + " - " + it.getCategory())
                    .collect(Collectors.joining("\n"));

            String prompt = "用户偏好: " + profile + "\n推荐图书:\n" + bookList;
            String reply = llmClient.chat(SYSTEM_PROMPT, prompt);
            if (reply == null) {
                return Collections.emptyMap();
            }
            return parseReasons(reply);
        } catch (Exception e) {
            log.warn("推荐理由生成失败: {}", e.getMessage());
            return Collections.emptyMap();
        }
    }

    /**
     * 用户画像：高分书(>=7)的 Top-3 分类与 Top-5 作者
     */
    private String buildProfile(Long userId) {
        List<Rating> ratings = ratingMapper.findByUserId(userId);
        if (ratings == null || ratings.isEmpty()) {
            return "新用户，暂无历史偏好";
        }
        Map<String, Integer> catCount = new HashMap<>();
        Map<String, Integer> authCount = new HashMap<>();
        for (Rating r : ratings) {
            if (r.getScore() == null || r.getScore() < 7) {
                continue;
            }
            Book book = bookMapper.findById(r.getBookId());
            if (book == null) {
                continue;
            }
            if (book.getCategory() != null) {
                catCount.merge(book.getCategory(), 1, Integer::sum);
            }
            if (book.getAuthor() != null) {
                authCount.merge(book.getAuthor(), 1, Integer::sum);
            }
        }
        String cats = catCount.entrySet().stream()
                .sorted(Map.Entry.<String, Integer>comparingByValue().reversed())
                .limit(3).map(Map.Entry::getKey).collect(Collectors.joining("、"));
        String auths = authCount.entrySet().stream()
                .sorted(Map.Entry.<String, Integer>comparingByValue().reversed())
                .limit(5).map(Map.Entry::getKey).collect(Collectors.joining("、"));
        return "喜欢分类[" + (cats.isEmpty() ? "未知" : cats) + "]，喜欢的作者[" + (auths.isEmpty() ? "未知" : auths) + "]";
    }

    /**
     * 解析 LLM 返回的 JSON 数组（容忍 markdown 代码块包裹）
     */
    private Map<Long, String> parseReasons(String reply) {
        String json = reply.trim();
        int start = json.indexOf("[");
        int end = json.lastIndexOf("]");
        if (start < 0 || end < start) {
            return Collections.emptyMap();
        }
        try {
            JsonNode arr = objectMapper.readTree(json.substring(start, end + 1));
            Map<Long, String> result = new HashMap<>();
            for (JsonNode node : arr) {
                Long id = node.path("bookId").asLong();
                String reason = node.path("reason").asText("");
                if (id > 0 && !reason.isBlank()) {
                    result.put(id, reason);
                }
            }
            return result;
        } catch (Exception e) {
            log.warn("推荐理由 JSON 解析失败: {}", e.getMessage());
            return Collections.emptyMap();
        }
    }
}
