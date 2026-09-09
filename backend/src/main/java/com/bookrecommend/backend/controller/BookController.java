package com.bookrecommend.backend.controller;

import com.bookrecommend.backend.entity.Book;
import com.bookrecommend.backend.service.BookService;
import com.bookrecommend.backend.service.SimilarBookService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/book")
@RequiredArgsConstructor
public class BookController {

    private final BookService bookService;
    private final SimilarBookService similarBookService;

    /**
     * 图书列表（分页）
     */
    @GetMapping("/list")
    public Map<String, Object> list(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "24") int size,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String category
    ) {
        var result = bookService.listBooksPaged(page, size, keyword, category);
        result.put("code", 200);
        return result;
    }

    /**
     * 图书详情
     */
    @GetMapping("/{id}")
    public Map<String, Object> detail(@PathVariable Long id) {
        Book book = bookService.getBookById(id);
        return Map.of(
                "code", 200,
                "data", book
        );
    }

    /**
     * 相似图书 — "喜欢这本书的人也喜欢"
     */
    @GetMapping("/{id}/similar")
    public Map<String, Object> similar(
            @PathVariable Long id,
            @RequestParam(defaultValue = "6") int topN
    ) {
        List<Book> books = similarBookService.getSimilarBooks(id, topN);
        return Map.of(
                "code", 200,
                "data", books
        );
    }

}
