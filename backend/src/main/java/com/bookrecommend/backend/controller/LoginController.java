package com.bookrecommend.backend.controller;

import java.util.Map;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import com.bookrecommend.backend.dto.LoginRequest;
import com.bookrecommend.backend.service.SysUserService;

import lombok.RequiredArgsConstructor;

@RestController
@RequiredArgsConstructor
public class LoginController {

    private final SysUserService userService;

    @PostMapping("/user/login")
    public Map<String, Object> login(@RequestBody LoginRequest request) {

        String token = userService.login(
                request.getUsername(),
                request.getPassword()
        );

        return Map.of(
                "code", 200,
                "message", "登录成功",
                "token", token
        );

    }

}
