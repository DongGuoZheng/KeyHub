# -*- coding: utf-8 -*-
"""
手机相册备份 —— 电脑端接收服务
Python 标准库 / 零第三方依赖 / 单文件

启动:   python backup_server.py
配置:   环境变量 PHOTO_BACKUP_DIR 指定备份目录 (默认: 脚本同目录/received)

协议(极简, 不用 multipart):
  GET  /api/hello              服务探活
  POST /api/check              手机发文件指纹清单, 服务端返回未备份的 key
  POST /api/upload?key=&name=&mtime=&device=   请求体是文件原始字节
  GET  /                       浏览器状态页
  UDP  端口 51234              收到 MAGIC 广播则回复本机 HTTP 端口, 供手机自动发现
"""
import os
import sys
import json
import time
import socket
import hashlib
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ===================== 常量区 (Constants-First) =====================
SERVICE_NAME = "ZGGG-PhotoBackup"
HTTP_HOST = "0.0.0.0"
HTTP_PORT = 8899
UDP_PORT = 51234
UDP_MAGIC = b"ZGGG_PHOTO_DISCOVER_V1"
UDP_REPLY = "ZGGG_PHOTO_HERE_V1|%d|%s|%s"
DEFAULT_DIRNAME = "received"
PARTS_DIRNAME = ".parts"
INDEX_NAME = ".index.json"
PART_SUFFIX = ".part"
READ_CHUNK = 1 << 20
MAX_BODY_BYTES = 4 * 1024 * 1024 * 1024
ENV_DIR = "PHOTO_BACKUP_DIR"
PAGE_REFRESH = 5
RECENT_LIMIT = 40

# ===================== 路径 =====================
BASE_DIR = os.environ.get(ENV_DIR, "").strip() or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DIRNAME)
BASE_DIR = os.path.abspath(BASE_DIR)
PARTS_DIR = os.path.join(BASE_DIR, PARTS_DIRNAME)
INDEX_PATH = os.path.join(BASE_DIR, INDEX_NAME)

for _d in (BASE_DIR, PARTS_DIR):
    os.makedirs(_d, exist_ok=True)


# ===================== 工具 =====================
def safe_name(name, fallback="unnamed"):
    """清洗文件名, 去掉路径分隔符与非法字符"""
    bad = '\\/:*?"<>|\r\n\t'
    out = "".join("_" if c in bad or ord(c) < 32 else c for c in (name or ""))
    out = out.strip().strip(".")
    return out[:120] or fallback


def unique_path(path):
    """同名文件自动加序号, 不覆盖已有文件"""
    if not os.path.exists(path):
        return path
    root, ext = os.path.splitext(path)
    for i in range(1, 10000):
        cand = "%s_%d%s" % (root, i, ext)
        if not os.path.exists(cand):
            return cand
    return path


def human(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return "%.1f %s" % (n, unit) if unit != "B" else "%d B" % int(n)
        n /= 1024.0
    return "%.1f TB" % n


def lan_ip():
    """取本机局域网 IP (不发真实数据包, 只是查路由表)"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("223.5.5.5", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        print(line.encode("utf-8", "replace").decode("ascii", "replace"), flush=True)


# ===================== 索引 =====================
class Index(object):
    """keys:   指纹key -> 记录 (快速增量判断)
       hashes: sha256  -> 相对路径 (内容级去重, 同一张图只存一份)"""

    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.data = {"keys": {}, "hashes": {}}
        self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                self.data["keys"] = d.get("keys", {}) or {}
                self.data["hashes"] = d.get("hashes", {}) or {}
                log("索引已加载: %d 个文件" % len(self.data["keys"]))
        except FileNotFoundError:
            pass
        except Exception as e:
            log("索引加载失败(将重建): %s" % e)

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False)
        os.replace(tmp, self.path)

    def missing(self, keys):
        with self.lock:
            return [k for k in keys if k not in self.data["keys"]]

    def put(self, key, sha, rel, size, device):
        with self.lock:
            self.data["keys"][key] = {
                "hash": sha, "rel": rel, "size": size,
                "device": device, "ts": int(time.time()),
            }
            self.data["hashes"].setdefault(sha, rel)
            self.save()

    def stats(self):
        with self.lock:
            keys, hashes = self.data["keys"], self.data["hashes"]
            total = sum(v.get("size", 0) for v in keys.values())
            devices = {}
            for v in keys.values():
                devices[v.get("device", "?")] = devices.get(v.get("device", "?"), 0) + 1
            recent = sorted(keys.values(), key=lambda v: v.get("ts", 0), reverse=True)[:RECENT_LIMIT]
            return {
                "files": len(keys), "unique": len(hashes), "bytes": total,
                "devices": devices, "recent": recent,
            }


IDX = Index(INDEX_PATH)


# ===================== HTTP =====================
HTML_HEAD = (
    '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
    '<meta http-equiv="refresh" content="%d">'
    '<title>相册备份服务</title><style>'
    'body{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;'
    'margin:0;padding:28px;background:#f6f7f9;color:#1f2328}'
    'h1{font-size:19px;font-weight:600;margin:0 0 4px}'
    '.sub{color:#656d76;font-size:13px;margin-bottom:20px}'
    '.cards{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:22px}'
    '.card{background:#fff;border:1px solid #e3e6ea;border-radius:10px;'
    'padding:14px 20px;min-width:130px}'
    '.card .n{font-size:22px;font-weight:600}'
    '.card .l{font-size:12px;color:#656d76;margin-top:2px}'
    'table{border-collapse:collapse;width:100%%;background:#fff;'
    'border:1px solid #e3e6ea;border-radius:10px;overflow:hidden;font-size:13px}'
    'th{background:#f0f2f5;text-align:left;padding:9px 12px;font-weight:600;color:#444c56}'
    'td{padding:8px 12px;border-top:1px solid #eef0f2;word-break:break-all}'
    'h2{font-size:15px;font-weight:600;margin:24px 0 10px}'
    '.empty{color:#8b949e;font-size:13px;padding:14px}'
    '</style></head><body>'
) % PAGE_REFRESH

HTML_TAIL = '</body></html>'


class Handler(BaseHTTPRequestHandler):
    server_version = "ZGGGPhotoBackup/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # 默认日志太吵, 自己按需打印

    # ---------- 响应封装 ----------
    def _json(self, obj, code=200):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        try:
            self.wfile.write(raw)
        except Exception:
            pass

    def _html(self, body, code=200):
        raw = (HTML_HEAD + body + HTML_TAIL).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        try:
            self.wfile.write(raw)
        except Exception:
            pass

    def _err(self, msg, code=400):
        self._json({"error": msg}, code)

    # ---------- GET ----------
    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if p in ("/", "/index.html"):
            return self._page()
        if p == "/api/hello":
            return self._json({
                "service": SERVICE_NAME, "version": 1,
                "http_port": HTTP_PORT, "host": socket.gethostname(),
            })
        if p == "/api/stats":
            s = IDX.stats()
            return self._json({k: s[k] for k in ("files", "unique", "bytes", "devices")})
        if p == "/api/files":
            s = IDX.stats()
            return self._json({"recent": s["recent"]})
        self._err("not found", 404)

    def _page(self):
        s = IDX.stats()
        dev_rows = "".join(
            "<tr><td>%s</td><td>%d</td></tr>" % (safe_name(d), c)
            for d, c in sorted(s["devices"].items(), key=lambda x: -x[1])
        ) or '<tr><td colspan="2" class="empty">还没有设备上传</td></tr>'

        file_rows = "".join(
            "<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                safe_name(os.path.basename(v.get("rel", ""))),
                human(v.get("size", 0)),
                time.strftime("%m-%d %H:%M", time.localtime(v.get("ts", 0))),
            ) for v in s["recent"]
        ) or '<tr><td colspan="3" class="empty">还没有文件, 打开手机上的备份 App 点「开始备份」</td></tr>'

        body = (
            '<h1>手机相册备份服务</h1>'
            '<div class="sub">备份目录 %s &nbsp;·&nbsp; 局域网地址 %s:%d &nbsp;·&nbsp; %d 秒自动刷新</div>'
            '<div class="cards">'
            '<div class="card"><div class="n">%d</div><div class="l">已备份文件</div></div>'
            '<div class="card"><div class="n">%s</div><div class="l">占用空间</div></div>'
            '<div class="card"><div class="n">%d</div><div class="l">去重后唯一文件</div></div>'
            '<div class="card"><div class="n">%d</div><div class="l">设备数</div></div>'
            '</div>'
            '<h2>设备</h2><table><tr><th>设备名</th><th>文件数</th></tr>%s</table>'
            '<h2>最近备份</h2><table><tr><th>文件名</th><th>大小</th><th>时间</th></tr>%s</table>'
        ) % (BASE_DIR, lan_ip(), HTTP_PORT, PAGE_REFRESH,
             s["files"], human(s["bytes"]), s["unique"], len(s["devices"]),
             dev_rows, file_rows)
        self._html(body)

    # ---------- POST ----------
    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/api/check":
            return self._api_check()
        if u.path == "/api/upload":
            return self._api_upload(q)
        self._err("not found", 404)

    def _api_check(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as e:
            return self._err("bad json: %s" % e)
        keys = [it.get("key") for it in payload.get("items", []) if it.get("key")]
        missing = IDX.missing(keys)
        log("收到清单 %d 个, 其中 %d 个需要上传" % (len(keys), len(missing)))
        self._json({"missing": missing, "total": len(keys)})

    def _api_upload(self, q):
        def one(k, default=""):
            v = q.get(k)
            return v[0] if v else default

        key = one("key")
        name = one("name")
        device = safe_name(one("device"), "unknown")
        try:
            mtime = int(float(one("mtime", "0")))
        except ValueError:
            mtime = 0
        if not key or not name:
            return self._err("missing key/name")

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            return self._err("empty body")
        if length > MAX_BODY_BYTES:
            return self._err("file too large")

        safe_fn = safe_name(name)
        tmp = os.path.join(PARTS_DIR, hashlib.md5(key.encode("utf-8")).hexdigest() + PART_SUFFIX)
        sha = hashlib.sha256()
        written = 0
        try:
            with open(tmp, "wb") as f:
                while written < length:
                    chunk = self.rfile.read(min(READ_CHUNK, length - written))
                    if not chunk:
                        break
                    f.write(chunk)
                    sha.update(chunk)
                    written += len(chunk)
        except Exception as e:
            try:
                os.remove(tmp)
            except OSError:
                pass
            return self._err("write failed: %s" % e, 500)

        if written != length:
            try:
                os.remove(tmp)
            except OSError:
                pass
            return self._err("incomplete body: %d/%d" % (written, length))

        digest = sha.hexdigest()
        with IDX.lock:
            dup_rel = IDX.data["hashes"].get(digest)
        if dup_rel:
            try:
                os.remove(tmp)
            except OSError:
                pass
            IDX.put(key, digest, dup_rel, written, device)
            log("= 内容重复, 复用已有: %s (%s)" % (safe_fn, human(written)))
            return self._json({"status": "duplicate", "rel": dup_rel, "size": written})

        t = time.localtime(mtime) if mtime > 0 else time.localtime()
        folder = os.path.join(BASE_DIR, device, time.strftime("%Y", t), time.strftime("%Y-%m-%d", t))
        os.makedirs(folder, exist_ok=True)
        dst = unique_path(os.path.join(folder, safe_fn))
        os.replace(tmp, dst)
        rel = os.path.relpath(dst, BASE_DIR).replace("\\", "/")
        IDX.put(key, digest, rel, written, device)
        log("+ %s (%s) -> %s" % (safe_fn, human(written), rel))
        self._json({"status": "ok", "rel": rel, "size": written, "hash": digest})


# ===================== UDP 局域网发现 =====================
def udp_thread():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("", UDP_PORT))
    except Exception as e:
        log("UDP 发现服务启动失败(不影响手动填 IP): %s" % e)
        return
    log("UDP 发现服务已启动, 端口 %d" % UDP_PORT)
    while True:
        try:
            data, addr = s.recvfrom(1024)
        except Exception:
            continue
        if data.strip() == UDP_MAGIC:
            reply = (UDP_REPLY % (HTTP_PORT, SERVICE_NAME, socket.gethostname())).encode("utf-8")
            try:
                s.sendto(reply, addr)
                log("回应发现请求: %s" % addr[0])
            except Exception:
                pass


# ===================== 入口 =====================
def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    threading.Thread(target=udp_thread, daemon=True).start()
    httpd = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), Handler)
    httpd.daemon_threads = True

    print("=" * 56)
    print("  手机相册备份服务")
    print("=" * 56)
    print("  备份目录 : %s" % BASE_DIR)
    print("  本机地址 : http://%s:%d" % (lan_ip(), HTTP_PORT))
    print("  状态页面 : http://localhost:%d" % HTTP_PORT)
    print("  UDP 发现 : 端口 %d" % UDP_PORT)
    print("  已备份   : %d 个文件" % len(IDX.data["keys"]))
    print("-" * 56)
    print("  手机上打开备份 App -> 自动发现, 或手动填上面的地址")
    print("  Ctrl+C 停止")
    print("=" * 56)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
