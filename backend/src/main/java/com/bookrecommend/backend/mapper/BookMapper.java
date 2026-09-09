package com.bookrecommend.backend.mapper;

import com.bookrecommend.backend.entity.Book;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface BookMapper {

    /**
     * 查询所有图书（内部使用，无分页，无聚合）
     */
    List<Book> findAll();

    /**
     * 查询所有图书（轻量版，无 JOIN，用于相似度计算）
     */
    List<Book> findAllSimple();

    /**
     * 分页查询图书列表
     */
    List<Book> findPage(@Param("offset") int offset, @Param("size") int size);

    /**
     * 图书总数
     */
    int countAll();

    /**
     * 根据 ID 查询图书
     */
    Book findById(Long id);

    /**
     * 关键词搜索（语义检索降级路径）
     */
    List<Book> findByKeyword(@Param("keyword") String keyword);

}
