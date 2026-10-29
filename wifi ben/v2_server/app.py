"""
WiFi Shop Manager v2 - Local Web Server & Dynamic Voucher Engine
Designed to run with standard user privileges (Zero Administrator / UAC prompt).
Simply enable Windows Mobile Hotspot manually, and this server handles customer portals & dynamic vouchers.
"""
import sys
import os
import http.server
import socketserver
import threading
import json
import urllib.parse
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

import subprocess
import random

# Add core to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from core.voucher_manager import VoucherManager
from core.network_detector import check_mobile_hotspot_status, detect_hotspot_ip
from core.config import config

WEB_DIR = BASE_DIR / "web"
voucher_mgr = VoucherManager()

def run_hotspot_ctrl(action: str, ssid: str = "", password: str = "") -> dict:
    try:
        script = BASE_DIR / "hotspot_ctrl.ps1"
        if not script.exists():
            script = BASE_DIR.parent / "hotspot_ctrl.ps1"
        cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Action", action]
        if ssid: cmd.extend(["-SSID", ssid])
        if password: cmd.extend(["-Password", password])
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if res.stdout:
            return json.loads(res.stdout.strip())
    except Exception:
        pass
    return {}

class NonAdminRequestHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress spammy default HTTP access logs for clean console
        pass

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json_response(self, data: Any, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_file_response(self, file_path: Path, content_type: str):
        if not file_path.exists():
            self.send_error(404, "File Not Found")
            return

        with open(file_path, "rb") as f:
            content = f.read()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 1. API: Live Status & Hotspot Detection
        if path == "/api/status":
            net_info = check_mobile_hotspot_status()
            port = config.get("portal_port", 8080)
            data = {
                "hotspot_active": net_info["hotspot_active"],
                "server_ip": net_info["server_ip"],
                "portal_url": f"http://{net_info['server_ip']}:{port}/",
                "ssid": config.get("hotspot_ssid", "benhazem"),
                "password": config.get("hotspot_password", "12345678"),
                "shop_name": config.get("shop_name", "WiFi Shop Manager"),
                "wall_duration": config.get("default_duration_minutes", 60),
                "status_message": net_info["status_message"],
                "stats": voucher_mgr.get_stats()
            }
            self._send_json_response(data)
            return

        # 2. API: Vouchers List from SQLite
        if path == "/api/vouchers":
            vouchers = voucher_mgr.get_all_vouchers(limit=100)
            self._send_json_response(vouchers)
            return

        # 3. API: Active Connected Sessions
        if path == "/api/clients":
            active_sessions = voucher_mgr.get_active_sessions()
            self._send_json_response(active_sessions)
            return

        # 4. Static Web Assets
        if path in ("/", "/dashboard", "/admin", "/index.html"):
            self._send_file_response(WEB_DIR / "index.html", "text/html; charset=utf-8")
            return

        if path == "/index.css":
            self._send_file_response(WEB_DIR / "index.css", "text/css; charset=utf-8")
            return

        if path == "/index.js":
            self._send_file_response(WEB_DIR / "index.js", "application/javascript; charset=utf-8")
            return

        # Fallback to local files if requested
        candidate = WEB_DIR / path.lstrip("/")
        if candidate.exists() and candidate.is_file():
            mime = "text/plain"
            if candidate.suffix == ".html": mime = "text/html; charset=utf-8"
            elif candidate.suffix == ".css": mime = "text/css; charset=utf-8"
            elif candidate.suffix == ".js": mime = "application/javascript; charset=utf-8"
            elif candidate.suffix in (".png", ".jpg", ".ico"): mime = f"image/{candidate.suffix.lstrip('.')}"
            self._send_file_response(candidate, mime)
            return

        # Default 404
        self.send_error(404, "Page Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        client_ip = self.client_address[0] if self.client_address else "192.168.137.2"

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else ""

        try:
            body = json.loads(post_data) if post_data else {}
        except Exception:
            body = {}

        # 1. API: Create Voucher
        if path == "/api/vouchers/create":
            default_dur = config.get("default_duration_minutes", 60)
            duration = int(body.get("duration", default_dur))
            price = float(body.get("price", 0.0))
            notes = str(body.get("notes", ""))

            voucher = voucher_mgr.create_voucher(duration_minutes=duration, price=price, notes=notes)
            self._send_json_response({"success": True, "voucher": voucher})
            return

        # 2. API: Revoke Voucher
        if path == "/api/vouchers/revoke":
            code = body.get("code", "")
            success = voucher_mgr.revoke_voucher(code)
            self._send_json_response({"success": success})
            return

        # 3. API: Manually Extend Session (+X minutes)
        if path == "/api/sessions/extend":
            code = body.get("code", "")
            minutes = int(body.get("minutes", 30))
            success, msg, data = voucher_mgr.extend_session(code, minutes)
            self._send_json_response({
                "success": success,
                "message": msg,
                "data": data
            })
            return

        # 4. API: Update Wall Poster Duration
        if path == "/api/settings/wall-duration":
            new_dur = int(body.get("duration", 60))
            config.set("default_duration_minutes", new_dur)
            self._send_json_response({
                "success": True,
                "duration": new_dur,
                "message": f"تم حفظ مدة كود الحائط إلى {new_dur} دقيقة بنجاح!"
            })
            return

        # 4b. API: Toggle Mobile Hotspot
        if path == "/api/hotspot/toggle":
            net_info = check_mobile_hotspot_status()
            action = "stop" if net_info["hotspot_active"] else "start"
            res = run_hotspot_ctrl(action)
            self._send_json_response({
                "success": True,
                "active": res.get("active", not net_info["hotspot_active"]),
                "ssid": config.get("hotspot_ssid", "benhazem"),
                "password": config.get("hotspot_password", "12345678")
            })
            return

        # 4c. API: Generate New Random Password
        if path == "/api/hotspot/generate-password":
            new_pass = str(random.randint(10000000, 99999999))
            config.set("hotspot_password", new_pass)
            threading.Thread(target=run_hotspot_ctrl, args=("set", config.get("hotspot_ssid", "benhazem"), new_pass), daemon=True).start()
            self._send_json_response({
                "success": True,
                "password": new_pass,
                "ssid": config.get("hotspot_ssid", "benhazem"),
                "message": "تم توليد كلمة سر جديدة وتطبيقها في ويندوز فوراً!"
            })
            return

        # 5. API: Update SSID / Password / Shop Name
        if path == "/api/settings/update":
            new_ssid = str(body.get("ssid", "")).strip()
            new_pass = str(body.get("password", "")).strip()
            changed_hotspot = False
            if new_ssid:
                config.set("hotspot_ssid", new_ssid)
                changed_hotspot = True
            if new_pass and len(new_pass) >= 8:
                config.set("hotspot_password", new_pass)
                changed_hotspot = True
            if "shop_name" in body:
                config.set("shop_name", str(body["shop_name"]).strip())

            if changed_hotspot:
                threading.Thread(
                    target=run_hotspot_ctrl,
                    args=("set", config.get("hotspot_ssid", "benhazem"), config.get("hotspot_password", "12345678")),
                    daemon=True
                ).start()

            self._send_json_response({
                "success": True,
                "ssid": config.get("hotspot_ssid"),
                "password": config.get("hotspot_password", "12345678"),
                "shop_name": config.get("shop_name"),
                "message": "تم تطبيق وتحديث إعدادات نقطة الاتصال في ويندوز فوراً!"
            })
            return

        # 6. Customer Portal: One-Tap Access from Wall Poster Scan
        if path == "/request-access":
            default_dur = config.get("default_duration_minutes", 60)
            success, msg, data = voucher_mgr.generate_on_demand_guest_session(
                client_ip=client_ip,
                default_duration=default_dur
            )
            self._send_json_response({
                "success": success,
                "message": msg,
                "voucher": data
            })
            return

        # 7. Customer Portal: Activate Voucher Code manually
        if path == "/api/vouchers/activate":
            code = body.get("code", "").strip()
            success, msg, data = voucher_mgr.activate_voucher(code=code, client_ip=client_ip)
            self._send_json_response({
                "success": success,
                "message": msg,
                "data": data
            })
            return

        self.send_error(404, "Not Found")

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def start_expiry_monitor():
    """Background worker that expires old vouchers every 5 seconds."""
    def worker():
        import time
        while True:
            try:
                voucher_mgr.check_and_expire_sessions()
            except Exception:
                pass
            time.sleep(5)

    t = threading.Thread(target=worker, daemon=True)
    t.start()

def main():
    port = config.get("portal_port", 8080)
    net_info = check_mobile_hotspot_status()
    server_ip = net_info["server_ip"]
    hotspot_ready = net_info["hotspot_active"]

    print("=" * 65)
    print("      📶 WiFi Shop Manager v2 - Local Web Server Engine       ")
    print("=" * 65)
    print(f"[*] إصدار بدون صلاحيات مسؤول (Zero Admin / UAC Prompt Required)")
    print(f"[*] عنوان الخادم المحلي (Server IP): http://{server_ip}:{port}/")
    print(f"[*] لوحة التحكم الرئيسية: http://localhost:{port}/dashboard")
    print("-" * 65)
    if hotspot_ready:
        print("[OK] نقطة اتصال ويندوز (Mobile Hotspot) مفعلة وجاهزة بنجاح! ✅")
    else:
        print("[تنبيه] يرجى التأكد من تشغيل (Mobile Hotspot) من إعدادات ويندوز")
        print("       ليتمكن الزبائن من الاتصال بشبكتك ومسح كود الـ QR. ⚠️")
    print("=" * 65)
    print("[*] جاري تشغيل الخادم والاستماع للطلبات... (اضغط Ctrl+C للإيقاف)")

    # Start background expiration checker
    start_expiry_monitor()

    # Automatically launch dashboard in default browser
    if config.get("auto_open_browser", True):
        def open_browser():
            import time
            time.sleep(0.8)
            webbrowser.open(f"http://localhost:{port}/dashboard")

        threading.Thread(target=open_browser, daemon=True).start()

    server = ThreadedHTTPServer(("0.0.0.0", port), NonAdminRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] إيقاف الخادم بأمان... تم الخروج.")
        server.shutdown()

if __name__ == "__main__":
    main()
