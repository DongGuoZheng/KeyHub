# -*- coding: utf-8 -*-
"""
ZGGG 安卓能力演示 App
=====================
用 Python (Kivy) 调用尽可能多的安卓原生能力。
每个能力都做了降级处理: 某项不可用不影响其他功能。
本地调试: python main.py (桌面环境会自动显示"非安卓环境"提示)
"""

import os
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import platform

IS_ANDROID = platform == "android"

# ---------------- 中文字体 ----------------
def _find_font():
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "NotoSansSC-Regular.otf"),
        os.path.join("fonts", "NotoSansSC-Regular.otf"),
        "C:/Windows/Fonts/msyh.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None

_font = _find_font()
if _font:
    LabelBase.register(name="cn", fn_regular=_font)
    FONT = "cn"
else:
    FONT = "Roboto"

# ---------------- 能力模块按需导入 ----------------
MODULES = {}

def _try_import(name, pkg=None):
    """安全导入, 失败返回 None 而不是崩溃"""
    try:
        if pkg:
            m = __import__(pkg, fromlist=[name])
            return getattr(m, name)
        m = __import__(name)
        return m
    except Exception:
        return None

for _n in ["accelerometer", "gyroscope", "light", "proximity", "compass",
           "battery", "vibrator", "flash", "notification", "tts",
           "clipboard", "gps", "storagepath", "camera", "uniqueid"]:
    MODULES[_n] = _try_import(_n, "plyer")

JNIUS = _try_import("autoclass", "jnius") if IS_ANDROID else None


def dev_info():
    """读取设备硬件信息 (安卓 Java API)"""
    if not JNIUS:
        return {"状态": "非安卓环境"}
    try:
        Build = JNIUS("android.os.Build")
        Version = JNIUS("android.os.Build$VERSION")
        return {
            "制造商": str(Build.MANUFACTURER),
            "型号": str(Build.MODEL),
            "品牌": str(Build.BRAND),
            "安卓版本": str(Version.RELEASE),
            "SDK 版本": str(Version.SDK_INT),
            "设备代号": str(Build.DEVICE),
        }
    except Exception as e:
        return {"错误": str(e)[:60]}


def android_id():
    """设备唯一 ID"""
    if not JNIUS:
        return "非安卓环境"
    try:
        Secure = JNIUS("android.provider.Settings$Secure")
        act = JNIUS("org.kivy.android.PythonActivity").mActivity
        return str(Secure.getString(act.getContentResolver(), Secure.ANDROID_ID))[:16] + "..."
    except Exception as e:
        return "读取失败: %s" % str(e)[:40]


def network_type():
    """当前网络类型 (WiFi / 移动数据 / 无网络)"""
    if not JNIUS:
        return "非安卓环境"
    try:
        act = JNIUS("org.kivy.android.PythonActivity").mActivity
        cm = act.getSystemService("connectivity")
        net = cm.getActiveNetworkInfo()
        if net is None or not net.isConnected():
            return "无网络连接"
        t = net.getTypeName()
        sub = net.getSubtypeName()
        return "%s (%s)" % (t, sub) if sub else str(t)
    except Exception as e:
        return "读取失败: %s" % str(e)[:40]


def screen_info():
    """屏幕参数"""
    from kivy.metrics import Metrics
    return {
        "分辨率": "%d x %d" % (Window.width, Window.height),
        "像素密度": "%.1f dpi" % Metrics.dpi,
        "缩放比": "%.2f" % Metrics.density,
    }


def storage_info():
    """存储空间"""
    out = {}
    try:
        base = MODULES.get("storagepath")
        if base:
            try:
                out["外部存储"] = str(base.get_external_storage_dir())[:34]
            except Exception:
                pass
    except Exception:
        pass
    try:
        st = os.statvfs("/storage/emulated/0" if IS_ANDROID else ".")
        total = st.f_blocks * st.f_frsize / 1024 ** 3
        free = st.f_bavail * st.f_frsize / 1024 ** 3
        out["总空间"] = "%.1f GB" % total
        out["可用空间"] = "%.1f GB" % free
    except Exception:
        out["存储"] = "读取失败"
    return out


def safe_read(obj, *attrs, default="N/A", fmt=None):
    """安全读取传感器属性 (不同平台属性名可能不同)"""
    for a in attrs:
        try:
            v = getattr(obj, a)
            if v is not None:
                return fmt(v) if fmt else v
        except Exception:
            continue
    return default


# ---------------- UI 组件 ----------------
class Card(BoxLayout):
    """带背景的卡片容器"""

    def __init__(self, title, **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None,
                         padding=[dp(14), dp(12), dp(14), dp(12)], spacing=dp(8), **kwargs)
        self.bind(minimum_height=self.setter("height"))
        with self.canvas.before:
            Color(0.95, 0.96, 0.98, 1)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
        self.bind(pos=self._sync, size=self._sync)

        t = Label(text=title, font_name=FONT, font_size=dp(17), bold=True,
                  size_hint_y=None, height=dp(26), halign="left", color=(0.05, 0.15, 0.35, 1))
        t.bind(size=lambda *a: setattr(t, "text_size", (t.width, None)))
        self.add_widget(t)

    def _sync(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def add_row(self, text, size=14, bold=False, color=(0.15, 0.15, 0.15, 1)):
        lb = Label(text=text, font_name=FONT, font_size=dp(size), bold=bold,
                   size_hint_y=None, height=dp(22), halign="left", color=color)
        lb.bind(size=lambda *a: setattr(lb, "text_size", (lb.width, None)))
        self.add_widget(lb)
        return lb

    def add_buttons(self, items):
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        for label, cb in items:
            b = Button(text=label, font_name=FONT, font_size=dp(14))
            b.bind(on_press=cb)
            row.add_widget(b)
        self.add_widget(row)
        return row


ACCEL_ON = {"v": False}
GYRO_ON = {"v": False}
SENSOR_ON = {"v": False}
GPS_ON = {"v": False}


class DemoScreen(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)

        header = Label(text="[b]ZGGG · 安卓能力演示[/b]", markup=True, font_name=FONT,
                       font_size=dp(24), size_hint_y=None, height=dp(48),
                       color=(0.05, 0.25, 0.55, 1))
        self.add_widget(header)

        sub = Label(text="Python + Kivy 调用安卓原生 API", font_name=FONT,
                    font_size=dp(13), size_hint_y=None, height=dp(22),
                    color=(0.45, 0.45, 0.45, 1))
        self.add_widget(sub)

        sv = ScrollView()
        self.body = BoxLayout(orientation="vertical", spacing=dp(12),
                              size_hint_y=None, padding=[dp(12), dp(8), dp(12), dp(20)])
        self.body.bind(minimum_height=self.body.setter("height"))
        sv.add_widget(self.body)
        self.add_widget(sv)

        self._build_device_card()
        self._build_sensor_card()
        self._build_battery_card()
        self._build_gps_card()
        self._build_hardware_card()
        self._build_system_card()
        self._build_storage_card()

        Clock.schedule_interval(self._tick, 0.5)

    # ---- 设备信息 ----
    def _build_device_card(self):
        c = Card("设备信息")
        info = dev_info()
        for k, v in info.items():
            c.add_row("%s: %s" % (k, v))
        c.add_row("设备 ID: %s" % android_id(), size=12)
        si = screen_info()
        for k, v in si.items():
            c.add_row("%s: %s" % (k, v), size=13)
        self.body.add_widget(c)

    # ---- 传感器 ----
    def _build_sensor_card(self):
        c = Card("传感器 (实时)")
        self.accel_lb = c.add_row("加速度: --")
        self.gyro_lb = c.add_row("陀螺仪: --")
        self.light_lb = c.add_row("光线: --")
        self.prox_lb = c.add_row("接近: --")
        self.compass_lb = c.add_row("罗盘: --")
        self.sensor_state = c.add_row("状态: 未启动", size=12, color=(0.5, 0.5, 0.5, 1))
        c.add_buttons([
            ("启动传感器", self.toggle_sensors),
            ("启动陀螺仪", self.toggle_gyro),
        ])
        self.body.add_widget(c)

    # ---- 电池 ----
    def _build_battery_card(self):
        c = Card("电池与电源")
        self.batt_lb = c.add_row("电量: --", size=15)
        c.add_buttons([("刷新电量", self.read_battery)])
        self.body.add_widget(c)

    # ---- GPS ----
    def _build_gps_card(self):
        c = Card("定位 GPS")
        self.gps_lb = c.add_row("经纬度: --")
        self.gps_ex_lb = c.add_row("海拔/速度: --", size=13)
        c.add_buttons([("开始定位", self.toggle_gps)])
        self.body.add_widget(c)

    # ---- 硬件控制 ----
    def _build_hardware_card(self):
        c = Card("硬件控制")
        c.add_row("点击按钮调用对应硬件", size=12, color=(0.5, 0.5, 0.5, 1))
        self.flash_lb = c.add_row("闪光灯: --", size=13)
        c.add_buttons([
            ("振动 1 秒", lambda *_: self.do_vibrate()),
            ("闪光灯开/关", lambda *_: self.toggle_flash()),
        ])
        self.body.add_widget(c)

    # ---- 系统功能 ----
    def _build_system_card(self):
        c = Card("系统功能")
        self.tts_input = TextInput(text="你好, 这是 Python 合成的语音",
                                   font_name=FONT, font_size=dp(14),
                                   size_hint_y=None, height=dp(40), multiline=False)
        c.add_widget(self.tts_input)
        c.add_buttons([
            ("朗读文本", lambda *_: self.do_tts()),
            ("发送通知", lambda *_: self.do_notify()),
        ])
        self.clip_lb = c.add_row("剪贴板: --", size=13)
        c.add_buttons([
            ("复制文本", lambda *_: self.do_copy()),
            ("读取剪贴板", lambda *_: self.do_paste()),
        ])
        self.body.add_widget(c)

    # ---- 存储与网络 ----
    def _build_storage_card(self):
        c = Card("存储与网络")
        info = storage_info()
        for k, v in info.items():
            c.add_row("%s: %s" % (k, v), size=13)
        c.add_row("网络: %s" % network_type(), size=13)
        self.body.add_widget(c)

    # ---- 定时刷新 ----
    def _tick(self, *_):
        if SENSOR_ON["v"]:
            acc = MODULES.get("accelerometer")
            if acc:
                v = safe_read(acc, "acceleration", default=None)
                if v:
                    self.accel_lb.text = "加速度: X %.2f  Y %.2f  Z %.2f" % tuple(v)
            lt = MODULES.get("light")
            if lt:
                v = safe_read(lt, "illumination", default=None)
                if v is not None:
                    self.light_lb.text = "光线: %.1f lux" % v
            px = MODULES.get("proximity")
            if px:
                v = safe_read(px, "proximity", default=None)
                if v is not None:
                    self.prox_lb.text = "接近: %s" % ("有物体" if v else "无物体")
            cp = MODULES.get("compass")
            if cp:
                v = safe_read(cp, "bearing", "field", default=None)
                if v is not None:
                    try:
                        self.compass_lb.text = "罗盘方位: %.1f°" % float(v)
                    except Exception:
                        pass
        if GYRO_ON["v"]:
            gy = MODULES.get("gyroscope")
            if gy:
                v = safe_read(gy, "rotation", "orientation", default=None)
                if v:
                    try:
                        self.gyro_lb.text = "陀螺仪: X %.2f  Y %.2f  Z %.2f" % tuple(v[:3])
                    except Exception:
                        pass

    # ---- 交互方法 ----
    def toggle_sensors(self, *_):
        SENSOR_ON["v"] = not SENSOR_ON["v"]
        try:
            for m in ["accelerometer", "light", "proximity", "compass"]:
                mod = MODULES.get(m)
                if not mod:
                    continue
                if SENSOR_ON["v"]:
                    mod.enable()
                else:
                    mod.disable()
            self.sensor_state.text = "状态: %s" % ("监听中 (0.5s 刷新)" if SENSOR_ON["v"] else "已停止")
        except Exception as e:
            self.sensor_state.text = "启动失败: %s" % str(e)[:40]

    def toggle_gyro(self, *_):
        GYRO_ON["v"] = not GYRO_ON["v"]
        gy = MODULES.get("gyroscope")
        if not gy:
            return
        try:
            gy.enable() if GYRO_ON["v"] else gy.disable()
        except Exception:
            pass

    def read_battery(self, *_):
        b = MODULES.get("battery")
        if not b:
            self.batt_lb.text = "电量: 不可用"
            return
        try:
            s = b.status
            pct = s.get("percentage", "?")
            chg = "充电中" if s.get("isCharging") else "未充电"
            self.batt_lb.text = "电量: %s%%  (%s)" % (pct, chg)
        except Exception as e:
            self.batt_lb.text = "读取失败: %s" % str(e)[:40]

    def toggle_gps(self, *_):
        g = MODULES.get("gps")
        if not g:
            self.gps_lb.text = "经纬度: 不可用"
            return
        GPS_ON["v"] = not GPS_ON["v"]
        if not GPS_ON["v"]:
            try:
                g.stop()
            except Exception:
                pass
            self.gps_lb.text = "经纬度: 已停止"
            return
        if IS_ANDROID:
            self._ensure_location_permission()
        try:
            g.configure(on_location=self._on_location, on_status=self._on_gps_status)
            g.start(minTime=1000, minDistance=1)
            self.gps_lb.text = "定位中... 请到户外或开窗"
        except Exception as e:
            self.gps_lb.text = "启动失败: %s" % str(e)[:50]

    def _ensure_location_permission(self):
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.ACCESS_FINE_LOCATION,
                                 Permission.ACCESS_COARSE_LOCATION])
        except Exception:
            pass

    def _on_location(self, **kw):
        lat = kw.get("lat")
        lon = kw.get("lon")
        if lat is None:
            return
        self.gps_lb.text = "纬度 %.5f  经度 %.5f" % (lat, lon)
        alt = kw.get("altitude")
        spd = kw.get("speed")
        self.gps_ex_lb.text = "海拔 %s m   速度 %s m/s" % (
            round(alt, 1) if alt else "--",
            round(spd, 1) if spd else "--")

    def _on_gps_status(self, stype, status):
        self.gps_ex_lb.text = "GPS 状态: %s / %s" % (stype, status)

    def do_vibrate(self):
        v = MODULES.get("vibrator")
        if v:
            try:
                v.vibrate(1.0)
            except Exception:
                pass

    def toggle_flash(self):
        f = MODULES.get("flash")
        if not f:
            self.flash_lb.text = "闪光灯: 不可用"
            return
        try:
            if getattr(self, "_flash_on", False):
                f.off()
                self._flash_on = False
                self.flash_lb.text = "闪光灯: 已关闭"
            else:
                f.on()
                self._flash_on = True
                self.flash_lb.text = "闪光灯: 已打开"
        except Exception as e:
            self.flash_lb.text = "闪光灯: %s" % str(e)[:30]

    def do_tts(self):
        t = MODULES.get("tts")
        if t:
            try:
                t.speak(self.tts_input.text)
            except Exception:
                pass

    def do_notify(self):
        n = MODULES.get("notification")
        if n:
            try:
                n.notify(title="ZGGG Demo",
                         message="来自 Python 的安卓通知 %s" % time.strftime("%H:%M:%S"))
            except Exception:
                pass

    def do_copy(self):
        c = MODULES.get("clipboard")
        if c:
            try:
                c.copy("ZGGG Python 剪贴板测试 %s" % time.strftime("%H:%M:%S"))
                self.clip_lb.text = "剪贴板: 已写入"
            except Exception as e:
                self.clip_lb.text = "写入失败: %s" % str(e)[:30]

    def do_paste(self):
        c = MODULES.get("clipboard")
        if c:
            try:
                self.clip_lb.text = "剪贴板: %s" % str(c.paste())[:40]
            except Exception as e:
                self.clip_lb.text = "读取失败: %s" % str(e)[:30]


class ZgggDemoApp(App):
    title = "ZGGG 能力演示"

    def build(self):
        return DemoScreen()


if __name__ == "__main__":
    ZgggDemoApp().run()
