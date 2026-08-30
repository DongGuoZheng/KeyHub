[app]

# 应用名 (显示在手机桌面上的名字)
title = ZGGG Demo

# 包名 (安卓唯一标识, 反域名格式, 不要用 com.example)
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
# 必须锁定 Python 3.11! p4a 默认用 3.14, 但 pyjnius 等依赖还没有
# 3.14 的安卓预编译包, 会报 "No matching distribution found for pyjnius"
requirements = python3==3.11.9,kivy==2.3.0

# 打包引导方式 (sdl2 是标准方案, 不要动)
p4a.bootstrap = sdl2

# 权限 (最小化, 示例不需要任何权限)
android.permissions =

# 架构: arm64-v8a 覆盖 2017 年后几乎所有手机, 打包更快体积更小
android.archs = arm64-v8a

# 最低安卓版本
android.minapi = 21

# API 级别 (Buildozer 会自动下载对应 SDK 平台)
android.api = 33

# 签名 (默认 debug 签名, 可直接安装)
android.private_key = None
android.keyalias = None

# 图标 (留空用默认图标; 有 icon.png 可放项目根目录)
# icon.filename = %(source.dir)s/icon.png

# 存储权限声明 (避免某些设备弹窗)
android.add_src =

# 日志级别
android.logcat_filters =

# 构建输出目录
buildozer.settings = 

[buildozer]

# 构建时下载文件存放目录
log_level = 2

warn_on_root = 1

# 允许外网下载 SDK/NDK 等
# (默认即允许, 无需额外配置)

# p4a 源 (默认 GitHub, 国内网络慢可改用镜像)
p4a.source_dir = 
p4a.local_recipes =
p4a.branch = develop

# Android SDK/NDK 版本 (Buildozer 自动下载)
android.ndk = 25b
android.sdk = 34

# 架构
android.archs = arm64-v8a
