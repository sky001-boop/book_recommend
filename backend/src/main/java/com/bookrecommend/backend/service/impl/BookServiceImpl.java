package com.bookrecommend.backend.service.impl;

import com.bookrecommend.backend.entity.Book;
import com.bookrecommend.backend.exception.BusinessException;
import com.bookrecommend.backend.mapper.BookMapper;
import com.bookrecommend.backend.service.BookService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class BookServiceImpl implements BookService {

    private final BookMapper bookMapper;

    @Override
    public List<Book> listBooks() {
        return bookMapper.findAll();
    }

    @Override
    public Map<String, Object> listBooksPaged(int page, int size, String keyword, String category) {
        // 先全量查（轻量查询无JOIN，22K条很快）
        List<Book> all = bookMapper.findAllSimple();

        // 内存过滤
        if (keyword != null && !keyword.isBlank()) {
            String kw = keyword.toLowerCase();
            all = all.stream()
                .filter(b -> (b.getTitle() != null && b.getTitle().toLowerCase().contains(kw))
                          || (b.getAuthor() != null && b.getAuthor().toLowerCase().contains(kw)))
                .toList();
        }
        if (category != null && !category.isBlank()) {
            all = all.stream()
                .filter(b -> category.equals(b.getCategory()))
                .toList();
        }

        int total = all.size();
        int offset = (page - 1) * size;
        List<Book> pageData = all.stream().skip(offset).limit(size).toList();

        Map<String, Object> result = new java.util.HashMap<>();
        result.put("total", total);
        result.put("page", page);
        result.put("size", size);
        result.put("data", pageData);
        return result;
    }

    @Override
    public Book getBookById(Long id) {
        Book book = bookMapper.findById(id);
        if (book == null) {
            throw new BusinessException(404, "图书不存在");
        }
        return book;
    }

}
