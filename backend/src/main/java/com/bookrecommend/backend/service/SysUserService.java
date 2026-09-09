package com.bookrecommend.backend.service;


import com.bookrecommend.backend.entity.SysUser;


public interface SysUserService {


    void register(SysUser user);


    String login(
            String username,
            String password
    );


}