# -*- coding: utf-8 -*-
"""
Kivy 安卓示例应用 —— ZGGG 计数器 Demo
=====================================
功能: 点击按钮计数 + 清零, 中文界面。
打包为 APK 后在安卓手机上运行。
本地调试:  python main.py   (Windows/Mac/Linux 直接出窗口)
"""

import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.core.text import LabelBase
from kivy.utils import platform

# ---------- 中文字体处理 ----------
# Kivy 默认字体不含中文, 安卓上会显示方块。
# 若项目 fonts/ 目录存在中文字体则加载, 保证打包后中文正常显示。
def _find_font():
    candidates = []
    # 1. 随 APK 打包的字体 (buildozer 会把 fonts/ 打进 assets)
    if platform == "android":
        candidates.append(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "fonts", "NotoSansSC-Regular.otf"))
    # 2. 本地开发时的字体
    candidates.append(os.path.join("fonts", "NotoSansSC-Regular.otf"))
    # 3. 兜底: 用系统已有中文字体
    candidates += [
        "C:/Windows/Fonts/msyh.ttc",          # Windows 微软雅黑
        "/System/Library/Fonts/PingFang.ttc",  # macOS 苹方
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None

_font = _find_font()
if _font:
    LabelBase.register(name="cn", fn_regular=_font)
    _FONT_NAME = "cn"
else:
    _FONT_NAME = "Roboto"


# ---------- 界面 ----------
class CounterScreen(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=30, spacing=20, **kwargs)

        # 标题
        title = Label(
            text="[b]ZGGG · Python 安卓 Demo[/b]",
            markup=True,
            font_name=_FONT_NAME,
            font_size=26,
            size_hint=(1, 0.15),
        )
        self.add_widget(title)

        # 计数显示
        self.count = 0
        self.count_label = Label(
            text="0",
            font_name=_FONT_NAME,
            font_size=120,
            bold=True,
            size_hint=(1, 0.45),
        )
        self.add_widget(self.count_label)

        # 提示文字
        hint = Label(
            text="点击下面按钮试试",
            font_name=_FONT_NAME,
            font_size=18,
            color=(0.6, 0.6, 0.6, 1),
            size_hint=(1, 0.1),
        )
        self.add_widget(hint)

        # 按钮区
        btn_row = BoxLayout(spacing=15, size_hint=(1, 0.2))
        plus_btn = Button(
            text="点我 +1",
            font_name=_FONT_NAME,
            font_size=24,
            background_color=(0.20, 0.60, 0.95, 1),
        )
        plus_btn.bind(on_press=self.on_plus)
        clear_btn = Button(
            text="清零",
            font_name=_FONT_NAME,
            font_size=24,
            background_color=(0.75, 0.30, 0.25, 1),
        )
        clear_btn.bind(on_press=self.on_clear)
        btn_row.add_widget(plus_btn)
        btn_row.add_widget(clear_btn)
        self.add_widget(btn_row)

    def on_plus(self, _btn):
        self.count += 1
        self.count_label.text = str(self.count)

    def on_clear(self, _btn):
        self.count = 0
        self.count_label.text = "0"


class ZgggDemoApp(App):
    title = "ZGGG Demo"

    def build(self):
        return CounterScreen()


if __name__ == "__main__":
    ZgggDemoApp().run()
