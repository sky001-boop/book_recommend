package com.bookrecommend.backend.utils;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;

public class JwtUtil {

    // HS256 要求密钥至少 256 bits（32 字节）
    private static final String SECRET =
            "BookRecommendSystemSecretKey2024!@#$%^&*()";

    private static final SecretKey KEY =
            Keys.hmacShaKeyFor(SECRET.getBytes(StandardCharsets.UTF_8));

    // Token 有效期：24 小时
    private static final long EXPIRATION = 1000 * 60 * 60 * 24;

    /**
     * 生成 JWT Token
     */
    public static String generateToken(String username) {

        return Jwts.builder()
                .subject(username)
                .issuedAt(new Date())
                .expiration(new Date(System.currentTimeMillis() + EXPIRATION))
                .signWith(KEY)
                .compact();

    }

    /**
     * 解析 Token，返回用户名
     */
    public static String parseToken(String token) {

        return Jwts.parser()
                .verifyWith(KEY)
                .build()
                .parseSignedClaims(token)
                .getPayload()
                .getSubject();

    }

}
