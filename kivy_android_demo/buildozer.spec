[app]

# 应用名 (显示在手机桌面上的名字)
title = ZGGG Demo

# 包名 (安卓唯一标识, 反域名格式)
package.name = zgggdemo
package.domain = org.zggg

# 源码入口
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,otf,ttf
source.include_patterns = fonts/*.otf,fonts/*.ttf

# 版本
version = 0.1
version.release = 0.1

# Python 与依赖库
# 用 p4a 默认 Python (3.14.x): p4a 已为其适配 NDK r28 的补丁。
# 手动指定 3.11 会导致 grpmodule.c 与 NDK r28 不兼容而编译失败。
requirements = python3,kivy==2.3.0

# 打包引导方式 (sdl2 标准方案)
p4a.bootstrap = sdl2

# 权限 (示例不需要任何权限)
android.permissions =

# 架构: 只打 arm64-v8a, 覆盖 2017 年后几乎所有手机, 构建更快
android.archs = arm64-v8a

# ============================================================
# 重要: 不要自定义下面这几项!
# buildozer 默认是 minapi=24 / api=36 / ndk=28c,
# 官方预编译 wheel (pyjnius 等) 就是按这些默认值构建的。
# 改成别的值会导致找不到匹配平台的 wheel
# ("No matching distribution found for pyjnius")。
# 实测踩坑:
#   - minapi=21 -> 找 android_21_* wheel, 找不到
#   - ndk=25b   -> 若写错配置段落则不生效
# ============================================================
# android.minapi = 24
# android.api = 36
# android.ndk = 28c

[buildozer]

log_level = 2
warn_on_root = 1

# p4a 分支
p4a.branch = develop
