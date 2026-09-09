package com.bookrecommend.backend.service.impl;


import com.bookrecommend.backend.entity.SysUser;
import com.bookrecommend.backend.mapper.SysUserMapper;
import com.bookrecommend.backend.service.SysUserService;
import com.bookrecommend.backend.exception.BusinessException;
import com.bookrecommend.backend.utils.JwtUtil;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;



@Service
@RequiredArgsConstructor
public class SysUserServiceImpl implements SysUserService {


    private final SysUserMapper userMapper;
    private final PasswordEncoder passwordEncoder;


    @Override
    public void register(SysUser user) {

        // 默认普通用户
        user.setRole("USER");

        // BCrypt 加密密码
        user.setPassword(passwordEncoder.encode(user.getPassword()));

        userMapper.insert(user);

    }


    @Override
    public String login(String username, String password) {

        SysUser user = userMapper.findByUsername(username);

        if (user == null) {
            throw new BusinessException(400, "用户不存在");
        }

        // BCrypt 密码比对
        if (!passwordEncoder.matches(password, user.getPassword())) {
            throw new BusinessException(400, "密码错误");
        }

        return JwtUtil.generateToken(username);

    }

}
