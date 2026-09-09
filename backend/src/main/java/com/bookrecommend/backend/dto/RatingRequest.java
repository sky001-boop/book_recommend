package com.bookrecommend.backend.dto;

import lombok.Data;

@Data
public class RatingRequest {

    private Long bookId;

    private Float score;

}
