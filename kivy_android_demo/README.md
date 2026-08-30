# ZGGG Demo — Python 安卓示例

用 **Python + Kivy** 写的安卓小应用：点击计数 + 清零，中文界面。

## 项目结构
```
kivy_demo/
├── main.py                    # 应用源码 (Kivy)
├── buildozer.spec             # APK 打包配置
├── fonts/NotoSansSC-Regular.otf  # 开源中文字体 (保证安卓中文正常)
└── .github/workflows/build-apk.yml  # GitHub Actions 云打包
```

## 本地运行 (Windows/Mac/Linux 直接看效果)
```bash
pip install kivy
python main.py
```

## 打包 APK 的三种方式

### 方式 A: GitHub Actions 云打包 (推荐, 零环境折腾) ⭐
1. 在 GitHub 新建仓库, 把本目录所有文件推上去 (包含 `.github/`)
2. 进入仓库 **Actions** 页面, workflow `Build APK` 会自动运行 (或手动 `Run workflow`)
3. 等 20-40 分钟, 在 workflow 运行页底部 **Artifacts** 下载 APK
4. APK 传到手机, 允许"安装未知来源应用"后安装

### 方式 B: WSL2 + Buildozer 本地打包
```bash
# 在 WSL2 (Ubuntu) 里:
sudo apt update && sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config zlib1g-dev libncurses-dev cmake libffi-dev libssl-dev
pip3 install --user buildozer
cd kivy_demo
buildozer android debug
# 产出 bin/zgggdemo-0.1-arm64-v8a-debug.apk
```
首次构建要下载 SDK/NDK 并编译 Python, 约 1-2 小时。

### 方式 C: Termux 快速体验 (不打包, 手机上直接跑)
```bash
pkg install python
pip install kivy
# 手机连鼠标键盘或用 Termux 的 X11 方案运行 main.py
```

## 安装到手机
- 把 `*.apk` 传到手机 (微信/网盘/数据线都行)
- 点击安装, 如提示"未知来源", 在设置里允许该来源
- 桌面出现 "ZGGG Demo" 图标, 点开即用

## 后续扩展思路
- 换成自己的业务: 改 `main.py` 即可
- 加图标: 放一张 `icon.png` (512x512) 到项目根目录, spec 里取消注释
- 发布正式版: 生成签名 key, 用 `buildozer android release` 打包
