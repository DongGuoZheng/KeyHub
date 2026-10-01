# -*- coding: utf-8 -*-
"""
手机相册备份 —— 安卓端 (Kivy)

流程: 扫描 MediaStore -> 指纹清单问服务端要传哪些 -> 只传没备份过的 -> 局域网 HTTP 上传
运行: 手机上打开后点「扫描局域网」找到电脑, 或手动填 http://192.168.x.x:8899
"""
import os
import sys
import json
import time
import socket
import threading
import urllib.request
import urllib.error
import urllib.parse

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

# ===================== 常量区 (Constants-First) =====================
__version__ = "0.1"
APP_TITLE = "相册备份"
DEFAULT_PORT = 8899
UDP_PORT = 51234
UDP_MAGIC = b"ZGGG_PHOTO_DISCOVER_V1"
UDP_REPLY_PREFIX = "ZGGG_PHOTO_HERE_V1"
DISCOVER_TIMEOUT = 2.0
HTTP_TIMEOUT = 8
UPLOAD_TIMEOUT = 180
CHECK_BATCH = 500
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".bmp")
VIDEO_EXT = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".3gp")
FONT_PATH = "fonts/NotoSansSC-Regular.otf"

IS_ANDROID = hasattr(sys, "getandroidapilevel") or "ANDROID_ARGUMENT" in os.environ


# ===================== 安卓能力封装 (全部可降级) =====================
def _try_import(name, pkg=None):
    try:
        return __import__(name, fromlist=[pkg] if pkg else [])
    except Exception:
        return None


def android_activity():
    jnius = _try_import("jnius")
    if not jnius:
        return None
    try:
        act = jnius.autoclass("org.kivy.android.PythonActivity")
        return act.mActivity
    except Exception:
        return None


def keep_screen_on():
    """备份期间保持屏幕常亮, 防止系统休眠中断传输"""
    try:
        from jnius import autoclass
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        flags = autoclass("android.view.WindowManager$LayoutParams")
        activity.getWindow().addFlags(flags.FLAG_KEEP_SCREEN_ON)
        return True
    except Exception:
        return False


def sdk_int():
    try:
        from jnius import autoclass
        return autoclass("android.os.Build").VERSION.SDK_INT
    except Exception:
        return 0


def device_name():
    try:
        from jnius import autoclass
        b = autoclass("android.os.Build")
        return "%s_%s" % (b.MANUFACTURER, b.MODEL)
    except Exception:
        return "unknown-device"


def ensure_permissions(include_video):
    """Android 13+ 用 READ_MEDIA_IMAGES/VIDEO, 旧版用 READ_EXTERNAL_STORAGE"""
    if not IS_ANDROID:
        return True
    try:
        from android.permissions import request_permissions, check_permission
        from jnius import autoclass
        Manifest = autoclass("android.Manifest$permission")
    except Exception:
        return True

    names = ["READ_MEDIA_IMAGES"] if sdk_int() >= 33 else ["READ_EXTERNAL_STORAGE"]
    if include_video:
        names.append("READ_MEDIA_VIDEO" if sdk_int() >= 33 else "READ_EXTERNAL_STORAGE")

    granted, missing = [], []
    for n in names:
        perm = getattr(Manifest, n, None) or n
        try:
            (granted if check_permission(perm) else missing).append(perm)
        except Exception:
            missing.append(perm)
    if not missing:
        return True
    try:
        request_permissions(missing)
    except Exception:
        pass
    return False


def scan_media(include_video):
    """扫描 MediaStore 相册。分区存储下不能直接扫目录, 必须走 ContentResolver"""
    if not IS_ANDROID:
        return scan_media_desktop(include_video)

    try:
        from jnius import autoclass
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        resolver = activity.getContentResolver()
        Media = autoclass("android.provider.MediaStore")
    except Exception as e:
        print("MediaStore 不可用: %s" % e)
        return []

    out = []
    uris = [(Media.Images.Media.EXTERNAL_CONTENT_URI, False)]
    if include_video:
        uris.append((Media.Video.Media.EXTERNAL_CONTENT_URI, True))

    for uri, _ in uris:
        cursor = None
        try:
            cursor = resolver.query(uri, None, None, None, "_id ASC")
            if cursor is None:
                continue
            i_id = cursor.getColumnIndex("_id")
            i_name = cursor.getColumnIndex("_display_name")
            i_size = cursor.getColumnIndex("size")
            i_mt = cursor.getColumnIndex("date_modified")
            i_data = cursor.getColumnIndex("_data")
            while cursor.moveToNext():
                try:
                    path = cursor.getString(i_data) if i_data >= 0 else None
                    if not path or not os.path.exists(path):
                        continue
                    name = cursor.getString(i_name) or os.path.basename(path)
                    size = cursor.getLong(i_size) if i_size >= 0 else os.path.getsize(path)
                    mtime = int(cursor.getLong(i_mt)) if i_mt >= 0 else int(os.path.getmtime(path))
                    out.append({
                        "id": cursor.getLong(i_id), "path": path, "name": name,
                        "size": int(size), "mtime": mtime,
                        "key": "%s|%d|%d" % (name, size, mtime),
                    })
                except Exception:
                    continue
        except Exception as e:
            print("查询失败: %s" % e)
        finally:
            try:
                if cursor:
                    cursor.close()
            except Exception:
                pass
    return out


def scan_media_desktop(include_video):
    """桌面预览用: 扫当前目录的图片充当假相册"""
    exts = IMAGE_EXT + (VIDEO_EXT if include_video else ())
    out = []
    for root, _dirs, files in os.walk(os.getcwd()):
        for fn in files:
            if fn.lower().endswith(exts):
                p = os.path.join(root, fn)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                out.append({
                    "id": 0, "path": p, "name": fn, "size": st.st_size,
                    "mtime": int(st.st_mtime),
                    "key": "%s|%d|%d" % (fn, st.st_size, int(st.st_mtime)),
                })
        break
    return out


# ===================== 网络 =====================
def normalize_server(text):
    s = (text or "").strip()
    if not s:
        return ""
    if "://" not in s:
        s = "http://" + s
    u = urllib.parse.urlparse(s)
    host = u.hostname
    if not host:
        return ""
    return "http://%s:%d" % (host, u.port or DEFAULT_PORT)


def discover_servers():
    """UDP 广播发现局域网内的备份服务"""
    found = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.settimeout(DISCOVER_TIMEOUT)
        s.sendto(UDP_MAGIC, ("255.255.255.255", UDP_PORT))
        deadline = time.time() + DISCOVER_TIMEOUT
        while time.time() < deadline:
            try:
                data, addr = s.recvfrom(1024)
            except socket.timeout:
                break
            except Exception:
                break
            txt = data.decode("utf-8", "ignore")
            if txt.startswith(UDP_REPLY_PREFIX):
                parts = txt.split("|")
                port = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else DEFAULT_PORT
                label = parts[3] if len(parts) > 3 else parts[2] if len(parts) > 2 else "电脑"
                entry = "http://%s:%d" % (addr[0], port)
                if entry not in [f[0] for f in found]:
                    found.append((entry, label, addr[0]))
        s.close()
    except Exception as e:
        print("广播失败: %s" % e)
    return found


def api_check(base, items, device):
    """问服务端哪些文件还没备份过"""
    missing = []
    for i in range(0, len(items), CHECK_BATCH):
        batch = [{"key": it["key"], "name": it["name"],
                  "size": it["size"], "mtime": it["mtime"]} for it in items[i:i + CHECK_BATCH]]
        body = json.dumps({"device": device, "items": batch}).encode("utf-8")
        req = urllib.request.Request(base + "/api/check", data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            missing += json.loads(r.read().decode("utf-8")).get("missing", [])
    return missing


def api_upload(base, item, device):
    """流式上传单个文件, 不整块读进内存"""
    q = urllib.parse.urlencode({
        "key": item["key"], "name": item["name"],
        "mtime": item["mtime"], "device": device,
    })
    url = "%s/api/upload?%s" % (base, q)
    with open(item["path"], "rb") as f:
        req = urllib.request.Request(url, data=f, method="POST")
        req.add_header("Content-Length", str(item["size"]))
        with urllib.request.urlopen(req, timeout=UPLOAD_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))


def api_hello(base):
    with urllib.request.urlopen(base + "/api/hello", timeout=HTTP_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def human(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return "%.1f %s" % (n, unit) if unit != "B" else "%d B" % int(n)
        n /= 1024.0
    return "%.1f GB" % n


# ===================== UI =====================
FONT = FONT_PATH if os.path.exists(FONT_PATH) else None


def mk_label(text, size=14, color=(0.13, 0.15, 0.18, 1), height=None, bold=False):
    kw = dict(text=text, font_size=size, color=color, halign="left", valign="middle")
    if FONT:
        kw["font_name"] = FONT
    lab = Label(**kw)
    if height:
        lab.size_hint_y = None
        lab.height = height
    lab.bind(size=lambda *a: setattr(lab, "text_size", (lab.width - 8, None)))
    return lab


def mk_button(text, height=44):
    b = Button(text=text, font_size=15, size_hint_y=None, height=height)
    if FONT:
        b.font_name = FONT
    return b


class RootWidget(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=14, spacing=8, **kw)
        self.running = False
        self.items = []
        self.cancel = False

        head = mk_label("手机相册备份", size=20, bold=True, height=36)
        self.add_widget(head)
        self.add_widget(mk_label("同一 WiFi 下, 把相册备份到电脑", size=12,
                                 color=(0.42, 0.45, 0.5, 1), height=22))

        row1 = BoxLayout(size_hint_y=None, height=44, spacing=6)
        self.url_input = TextInput(text="", hint_text="电脑地址 如 192.168.1.5",
                                   font_size=14, multiline=False)
        if FONT:
            self.url_input.font_name = FONT
        self.btn_scan = mk_button("扫描", height=44)
        self.btn_scan.size_hint_x = 0.28
        self.btn_scan.bind(on_release=self.on_discover)
        self.btn_test = mk_button("测试", height=44)
        self.btn_test.size_hint_x = 0.28
        self.btn_test.bind(on_release=self.on_test)
        row1.add_widget(self.url_input)
        row1.add_widget(self.btn_scan)
        row1.add_widget(self.btn_test)
        self.add_widget(row1)

        row2 = BoxLayout(size_hint_y=None, height=38, spacing=6)
        self.video_cb = CheckBox(size_hint_x=None, width=44)
        row2.add_widget(self.video_cb)
        row2.add_widget(mk_label("同时备份视频 (体积大, 建议 WiFi 空闲时勾选)",
                                 size=13, color=(0.35, 0.38, 0.42, 1)))
        self.add_widget(row2)

        self.btn_start = mk_button("开始备份", height=52)
        self.btn_start.background_color = (0.11, 0.42, 0.75, 1)
        self.btn_start.bind(on_release=self.on_start)
        self.add_widget(self.btn_start)

        self.btn_stop = mk_button("停止", height=40)
        self.btn_stop.background_color = (0.75, 0.3, 0.28, 1)
        self.btn_stop.bind(on_release=self.on_stop)
        self.add_widget(self.btn_stop)

        self.progress = ProgressBar(max=100, value=0, size_hint_y=None, height=16)
        self.add_widget(self.progress)
        self.status = mk_label("就绪", size=13, color=(0.2, 0.35, 0.55, 1), height=26)
        self.add_widget(self.status)

        self.log_label = mk_label("", size=12, color=(0.25, 0.28, 0.32, 1))
        self.log_label.valign = "top"
        sc = ScrollView(size_hint=(1, 1))
        sc.add_widget(self.log_label)
        self.add_widget(sc)

    # ---------- 日志 (线程安全) ----------
    def log(self, msg):
        Clock.schedule_once(lambda dt: self._log_ui(msg))

    def _log_ui(self, msg):
        stamp = time.strftime("%H:%M:%S")
        self.log_label.text = "%s[%s] %s\n" % (self.log_label.text, stamp, msg)
        self.log_label.texture_update()
        self.log_label.height = max(self.log_label.texture_size[1], 1)

    def set_status(self, msg):
        Clock.schedule_once(lambda dt: setattr(self.status, "text", msg))

    def set_progress(self, done, total):
        def _u(dt):
            self.progress.max = max(total, 1)
            self.progress.value = done
        Clock.schedule_once(_u)

    # ---------- 交互 ----------
    def on_discover(self, *a):
        self.log("正在局域网广播查找电脑...")
        self.btn_scan.disabled = True

        def work():
            found = discover_servers()
            Clock.schedule_once(lambda dt: self._discover_done(found))

        threading.Thread(target=work, daemon=True).start()

    def _discover_done(self, found):
        self.btn_scan.disabled = False
        if not found:
            self.log("没扫到。检查: 电脑服务已启动 / 同一 WiFi / Windows 防火墙放行 UDP 51234")
            self.log("也可以手动填 IP, 例如 192.168.1.5")
            return
        for entry, label, ip in found:
            self.log("发现电脑: %s (%s) %s" % (ip, label, entry))
        self.url_input.text = found[0][0]
        self.log("已填入 %s" % found[0][0])

    def on_test(self, *a):
        base = normalize_server(self.url_input.text)
        if not base:
            self.log("请先填电脑地址或点扫描")
            return
        self.log("测试连接 %s ..." % base)

        def work():
            try:
                info = api_hello(base)
                self.log("连接成功: %s (端口 %s)" % (info.get("host"), info.get("http_port")))
            except Exception as e:
                self.log("连接失败: %s" % e)

        threading.Thread(target=work, daemon=True).start()

    def on_start(self, *a):
        if self.running:
            self.log("正在备份中")
            return
        base = normalize_server(self.url_input.text)
        if not base:
            self.log("先填电脑地址, 或点扫描自动查找")
            return
        self.running = True
        self.cancel = False
        self.btn_start.disabled = True
        threading.Thread(target=self._worker, args=(base, self.video_cb.active), daemon=True).start()

    def on_stop(self, *a):
        if self.running:
            self.cancel = True
            self.log("正在停止...")

    # ---------- 备份主流程 ----------
    def _worker(self, base, include_video):
        try:
            keep_screen_on()
            self.log("检查相册权限...")
            if not ensure_permissions(include_video):
                self.log("已向系统申请权限, 请在弹窗点允许, 然后再点一次「开始备份」")
                return

            self.set_status("正在扫描相册...")
            self.log("扫描相册 (视频: %s)..." % ("包含" if include_video else "不含"))
            items = scan_media(include_video)
            self.items = items
            self.log("扫描到 %d 个文件" % len(items))
            if not items:
                self.log("没扫到文件。若提示权限被拒, 到系统设置里手动授权相册权限")
                return

            device = device_name()
            self.set_status("比对增量...")
            self.log("向电脑询问哪些还没备份...")
            try:
                missing_keys = api_check(base, items, device)
            except Exception as e:
                self.log("比对失败: %s" % e)
                return

            todo = [it for it in items if it["key"] in set(missing_keys)]
            self.log("共 %d 个, 其中 %d 个需要上传" % (len(items), len(todo)))
            if not todo:
                self.set_status("已经是最新, 无需备份")
                self.log("全部已备份, 没有新文件")
                return

            done = ok = dup = fail = 0
            t0 = time.time()
            total_bytes = 0
            self.set_progress(0, len(todo))
            for it in todo:
                if self.cancel:
                    self.log("已手动停止")
                    break
                done += 1
                try:
                    r = api_upload(base, it, device)
                    if r.get("status") == "duplicate":
                        dup += 1
                        self.log("= 重复跳过 %s" % it["name"])
                    else:
                        ok += 1
                        total_bytes += it["size"]
                        self.log("+ %s (%s)" % (it["name"], human(it["size"])))
                except Exception as e:
                    fail += 1
                    self.log("x 失败 %s : %s" % (it["name"], e))
                self.set_progress(done, len(todo))
                self.set_status("已处理 %d/%d  成功 %d  重复 %d  失败 %d" % (
                    done, len(todo), ok, dup, fail))

            secs = max(time.time() - t0, 0.1)
            self.log("-" * 28)
            self.log("完成: 成功 %d / 重复 %d / 失败 %d, 传输 %s, 用时 %.0f 秒" % (
                ok, dup, fail, human(total_bytes), secs))
            self.set_status("备份完成  成功 %d  失败 %d" % (ok, fail))
        finally:
            self.running = False
            Clock.schedule_once(lambda dt: setattr(self.btn_start, "disabled", False))


class PhotoBackupApp(App):
    title = APP_TITLE

    def build(self):
        Window.softinput_mode = "below_target"
        return RootWidget()

    def on_pause(self):
        return True  # 切后台不退出, 备份继续


if __name__ == "__main__":
    PhotoBackupApp().run()
