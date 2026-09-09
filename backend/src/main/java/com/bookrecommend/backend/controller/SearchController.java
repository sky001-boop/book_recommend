package com.bookrecommend.backend.controller;

import com.bookrecommend.backend.entity.Book;
import com.bookrecommend.backend.llm.LlmClient;
import com.bookrecommend.backend.mapper.BookMapper;
import com.bookrecommend.backend.model.ModelServiceClient;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 自然语言找书（RAG 语义检索）
 *
 * 流程:
 *   1. 查询文本 -> 模型服务向量化（bge-small-zh）-> 与 22,808 本书向量余弦检索 Top-10
 *   2. 检索结果交给 LLM 组织成自然语言回答（可选，未配置 Key 时返回纯列表）
 * 降级: 模型服务不可用 -> 数据库关键词 LIKE 搜索
 */
@Slf4j
@RestController
@RequestMapping("/search")
@RequiredArgsConstructor
public class SearchController {

    private final ModelServiceClient modelClient;
    private final BookMapper bookMapper;
    private final LlmClient llmClient;

    @GetMapping("/nl")
    public Map<String, Object> naturalLanguageSearch(@RequestParam String q) {
        if (q == null || q.isBlank()) {
            return Map.of("code", 400, "message", "查询不能为空");
        }

        List<Book> books = semanticSearch(q);
        boolean degraded = false;
        if (books == null) {
            books = keywordSearch(q);
            degraded = true;
        }

        String answer = llmClient.isEnabled() && books != null && !books.isEmpty()
                ? buildAnswer(q, books)
                : null;

        List<Map<String, Object>> items = new ArrayList<>();
        if (books != null) {
            for (Book b : books) {
                items.add(Map.of(
                        "id", b.getId(),
                        "title", b.getTitle(),
                        "author", b.getAuthor(),
                        "category", b.getCategory() == null ? "" : b.getCategory(),
                        "cover", b.getCover() == null ? "" : b.getCover()
                ));
            }
        }
        return Map.of("code", 200, "data", items, "answer", answer == null ? "" : answer,
                "degraded", degraded);
    }

    /**
     * 语义检索（RAG）：模型服务 /search_nl
     */
    private List<Book> semanticSearch(String query) {
        try {
            List<Long> ids = modelClient.searchNL(query);
            if (ids == null || ids.isEmpty()) {
                return new ArrayList<>();
            }
            List<Book> books = new ArrayList<>();
            for (Long id : ids) {
                Book b = bookMapper.findById(id);
                if (b != null) {
                    books.add(b);
                }
            }
            return books;
        } catch (Exception e) {
            log.warn("语义检索失败，降级关键词搜索: {}", e.getMessage());
            return null;
        }
    }

    /**
     * 关键词降级：数据库 LIKE
     */
    private List<Book> keywordSearch(String query) {
        return bookMapper.findByKeyword(query);
    }

    /**
     * LLM 组织自然语言回答
     */
    private String buildAnswer(String query, List<Book> books) {
        String bookList = books.stream()
                .map(b -> b.getId() + ". 《" + b.getTitle() + "》(" + b.getAuthor() + ")"
                        + (b.getCategory() == null ? "" : "，分类:" + b.getCategory()))
                .collect(Collectors.joining("\n"));
        return llmClient.chat(
                "你是图书推荐助手。根据检索到的图书列表，用 2~3 句中文回答用户的问题，自然地介绍最相关的 1~3 本书。",
                "用户问题: " + query + "\n检索结果:\n" + bookList);
    }
}
