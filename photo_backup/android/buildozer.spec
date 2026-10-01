[app]

# 应用名 (显示在手机桌面上)
title = 监控直播

# 包名 (安卓唯一标识)
package.name = photobackup
package.domain = org.zggg

# 源码入口
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,otf,ttf
source.include_patterns = fonts/*.otf,fonts/*.ttf
source.exclude_dirs = bin,.buildozer

# version 与 version.regex 二选一, 不能同时写 (否则 buildozer 直接报错退出)
version = 0.3

# ============================================================
# 依赖配置 (沿用已验证组合, 请勿随意改动)
#   Kivy 2.3.0 不兼容 Python 3.14 (weakproxy.c 编译失败) -> 锁 3.11.9
#   hostpython3 必须与 python3 同版本, 否则 p4a 报版本不一致
#   plyer 供后续扩展 (电池/网络状态等), 纯 Python 走 pip 安装
# ============================================================
requirements = hostpython3==3.11.9,python3==3.11.9,kivy==2.3.0,plyer

p4a.bootstrap = sdl2

# ============================================================
# 权限 (对应 main.py 用到的安卓能力)
#   READ_MEDIA_IMAGES / READ_MEDIA_VIDEO : Android 13+ 相册读取 (运行时权限)
#   READ_EXTERNAL_STORAGE                : Android 12 及以下兼容
#   ACCESS_WIFI_STATE / ACCESS_NETWORK_STATE : 判断网络可用性
#   WAKE_LOCK                            : 备份期间保持唤醒
# ============================================================
android.permissions = INTERNET,READ_MEDIA_IMAGES,READ_MEDIA_VIDEO,READ_EXTERNAL_STORAGE,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,WAKE_LOCK

android.archs = arm64-v8a

# NDK / API (必须写在 [app] 段)
#   Python 3.11 只能配 NDK <= 25 (r26+ 移除 getgrent 等函数)
android.ndk = 25b
android.api = 33
android.minapi = 24

# 支持横竖屏切换
orientation = portrait

[buildozer]

log_level = 2
warn_on_root = 1
p4a.branch = develop
