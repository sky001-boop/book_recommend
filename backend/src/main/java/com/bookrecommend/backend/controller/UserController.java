package com.bookrecommend.backend.controller;


import com.bookrecommend.backend.entity.SysUser;
import com.bookrecommend.backend.service.SysUserService;


import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;



@RestController
@RequestMapping("/user")
@RequiredArgsConstructor
public class UserController {


    private final SysUserService userService;



    @PostMapping("/register")
    public String register(
            @RequestBody SysUser user
    ){


        userService.register(user);


        return "success";

    }

}