package com.bookrecommend.backend.entity;


import lombok.Data;

import java.time.LocalDateTime;


@Data
public class SysUser {


    private Long id;


    private String username;


    private String password;


    private String email;


    private String role;


    private LocalDateTime createTime;


}