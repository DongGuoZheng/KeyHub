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

# ============================================================
# 依赖配置 (踩坑总结, 请勿随意改动)
#
# 为什么锁 Python 3.11.9 而不是用默认的 3.14:
#   Kivy 2.3.0 的 Cython 生成代码不兼容 Python 3.14, 会报
#   "weakproxy.c: error: too few arguments to function call"
#
# 为什么 hostpython3 必须一起锁:
#   p4a 要求两者版本严格一致, 否则报
#   "python3 should have same version as hostpython3"
# ============================================================
# plyer: 安卓能力封装库 (传感器/电池/振动/通知/TTS/剪贴板/GPS/闪光灯)
# pyjnius 由 sdl2 bootstrap 自动引入, 无需显式声明
requirements = hostpython3==3.11.9,python3==3.11.9,kivy==2.3.0,plyer

# 打包引导方式 (sdl2 标准方案)
p4a.bootstrap = sdl2

# 权限声明 (对应 main.py 调用的安卓能力, 缺一个对应功能就静默失效)
android.permissions = INTERNET,VIBRATE,CAMERA,FLASHLIGHT,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,READ_PHONE_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# 架构: 只打 arm64-v8a, 覆盖 2017 年后几乎所有手机
android.archs = arm64-v8a

# ============================================================
# NDK / API 配置 (必须写在 [app] 段! 写错段落不生效)
#
# 为什么用 NDK 25b 而不是默认的 28c:
#   NDK r26+ 移除了 setgrent/getgrent/endgrent 等函数,
#   Python 3.11 的 grpmodule.c 编译会失败:
#   "error: call to undeclared function 'setgrent'"
#   NDK 25b 与 Python 3.11 是配套验证过的组合。
# ============================================================
android.ndk = 25b
android.api = 33
android.minapi = 24

[buildozer]

log_level = 2
warn_on_root = 1

# p4a 分支
p4a.branch = develop
