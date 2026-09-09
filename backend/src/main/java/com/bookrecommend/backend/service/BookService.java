package com.bookrecommend.backend.service;

import com.bookrecommend.backend.entity.Book;

import java.util.List;
import java.util.Map;

public interface BookService {

    /**
     * 获取全部图书列表（内部使用）
     */
    List<Book> listBooks();

    /**
     * 分页获取图书列表
     */
    Map<String, Object> listBooksPaged(int page, int size, String keyword, String category);

    /**
     * 获取图书详情
     */
    Book getBookById(Long id);

}
