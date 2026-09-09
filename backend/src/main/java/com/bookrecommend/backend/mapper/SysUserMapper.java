package com.bookrecommend.backend.mapper;


import com.bookrecommend.backend.entity.SysUser;
import org.apache.ibatis.annotations.Mapper;


@Mapper
public interface SysUserMapper {


    int insert(SysUser user);


    SysUser findByUsername(String username);

    Long findIdByUsername(String username);

}