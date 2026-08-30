# ZGGG Demo — Python 安卓 APK 示例

用 **Python + Kivy** 写的安卓应用：点击计数 + 清零，中文界面。
✅ **已成功打包为 APK**（33.1 MB，arm64-v8a，实测可安装到手机）。

## 快速开始

```bash
pip install kivy
python main.py          # 本地弹出窗口预览
```

## 打包成 APK（GitHub Actions 云端自动构建）

代码推到 GitHub 仓库后，Actions 自动触发，约 **12 分钟**出 APK。
产物在 Actions 运行页底部 **Artifacts** 下载。

### 文件结构要求

```
仓库根目录/
├── .github/workflows/build-apk.yml   ← 必须在根目录，GitHub 才识别
└── kivy_android_demo/                ← 源码放子目录（用 working-directory 切换）
    ├── main.py
    ├── buildozer.spec
    ├── fonts/    （CI 自动下载，不入库）
    └── .gitignore
```

## ⚠️ 踩过的 7 个坑（改配置前务必看）

这套工具链的版本耦合极紧，Python / NDK / Kivy / minapi 互相牵制。以下是实测踩坑记录：

| # | 现象 | 根因 | 解法 |
|---|---|---|---|
| 1 | 下载字体步骤失败 | `kivy/buildozer` 容器**没装 curl/wget** | 用容器自带的 `python3` + urllib 下载 |
| 2 | `EOFError: EOF when reading a line` | buildozer 检测到 **root 运行**，弹交互确认框，CI 无 stdin | `yes \| buildozer -v android debug` |
| 3 | `No matching distribution found for pyjnius` | `minapi` 设成 21，去找 `android_21_*` 的 wheel，官方包按默认 **24** 构建 | 用默认 `minapi=24` |
| 4 | `python3 should have same version as hostpython3` | 只锁了 python3，没锁 hostpython3 | 两个**一起锁且版本一致** |
| 5 | `grpmodule.c: undeclared function 'setgrent'` | NDK r26+ 移除了 getgrent 系列函数，Python 3.11 编译不过 | **NDK 降到 25b**（且必须写在 `[app]` 段） |
| 6 | `weakproxy.c: too few arguments` | **Kivy 2.3.0 不兼容 Python 3.14** | Python 用 3.11 |
| 7 | ✅ 成功 | — | 见下方配置 |

### 核心约束（记住这三条，别乱动版本）

```
Kivy 2.3.0    → 只能配 Python ≤ 3.13
Python 3.11   → 只能配 NDK ≤ 25
minapi        → 保持默认 24，改了会导致 wheel 平台标签不匹配
```

### 最终验证可用的配置

```ini
[app]
requirements = hostpython3==3.11.9,python3==3.11.9,kivy==2.3.0
p4a.bootstrap = sdl2
android.archs = arm64-v8a
android.ndk = 25b        # 必须在 [app] 段！写在 [buildozer] 段不生效
android.api = 33
android.minapi = 24
```

### 两个容易误判的现象

- **`grpmodule.c` 的 `setgrent` 报错是非致命的**：grp 模块 Android 用不到，构建会跳过继续。别被它误导去改配置。
- **Kivy 官方 wheel 索引（kivy.github.io/.../package-index/）实测 404**：p4a 会 fallback 到源码编译，慢但能成，不用管。

## 中文字体说明

Kivy 默认字体不含中文，安卓上会显示方块。本项目的处理：

- 字体文件 **16MB，不入库**（`.gitignore` 排除）
- CI 里用 python3 从 GitHub 下载思源黑体到 `fonts/`
- `main.py` 启动时自动检测并注册中文字体，找不到则回退系统字体

## 装到手机

1. APK 传到手机（微信 / 数据线 / 网盘）
2. 点开安装，提示「未知来源」时允许
3. 桌面出现 **ZGGG Demo** 图标

## 后续扩展

- 改业务逻辑：编辑 `main.py` 即可
- 换图标：放 `icon.png`（512×512）到项目根目录，spec 里取消注释
- 发布正式版：生成签名 key，改 `buildozer android release`
