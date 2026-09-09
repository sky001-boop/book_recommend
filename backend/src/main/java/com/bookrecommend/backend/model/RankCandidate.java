package com.bookrecommend.backend.model;

/**
 * 精排候选：多路召回通道的策略分（归一化后，0~1）
 * 后 4 个字段由召回侧计算，作为 DeepFM 精排模型的输入特征
 */
public record RankCandidate(
        Long bookId,
        double userCF,
        double itemCF,
        double content,
        double popular
) {
}
