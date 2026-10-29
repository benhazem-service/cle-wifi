"""
Captive Portal & Real Local REST API Web Server:
Serves the customer captive portal, hosts the dashboard, and provides real JSON APIs
backed directly by the SQLite database and Windows Wi-Fi controller (Zero Mock Data).
"""
import http.server
import socketserver
import threading
import urllib.parse
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from src.core.voucher_manager import VoucherManager
from src.core.wifi_controller import WiFiController
from src.utils.config import config, BASE_DIR

HTML_PAGE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{shop_name} - بوابة تسجيل الدخول إلى الواي فاي</title>
    <style>
        :root {{
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --bg: #090d16;
            --card-bg: rgba(30, 41, 59, 0.95);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --success: #10b981;
            --error: #ef4444;
            --border: #334155;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }}
        body {{
            background: linear-gradient(135deg, #090d16 0%, #1e1b4b 100%);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 1.25rem;
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 1.5rem;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
            width: 100%;
            max-width: 440px;
            padding: 2.25rem 2rem;
            text-align: center;
            backdrop-filter: blur(12px);
        }}
        .icon-circle {{
            width: 76px;
            height: 76px;
            border-radius: 50%;
            background: rgba(37, 99, 235, 0.18);
            color: #60a5fa;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 2.25rem;
            margin-bottom: 1.25rem;
            box-shadow: 0 0 25px rgba(37, 99, 235, 0.3);
        }}
        h1 {{
            font-size: 1.6rem;
            font-weight: 800;
            margin-bottom: 0.4rem;
        }}
        p.subtitle {{
            color: var(--text-muted);
            font-size: 0.95rem;
            margin-bottom: 1.75rem;
            line-height: 1.5;
        }}
        .btn-large {{
            width: 100%;
            padding: 1.1rem;
            background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);
            color: white;
            border: none;
            border-radius: 0.85rem;
            font-size: 1.1rem;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.25s;
            box-shadow: 0 8px 20px rgba(37, 99, 235, 0.4);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.6rem;
            text-decoration: none;
        }}
        .btn-large:hover {{
            transform: translateY(-2px);
            box-shadow: 0 12px 25px rgba(37, 99, 235, 0.5);
        }}
        .credentials-card {{
            display: {creds_display};
            background: rgba(15, 23, 42, 0.85);
            border: 2px solid #10b981;
            border-radius: 1rem;
            padding: 1.5rem;
            margin-top: 1.5rem;
            text-align: center;
        }}
        .cred-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.6rem 0;
            border-bottom: 1px dashed var(--border);
            font-size: 0.95rem;
        }}
        .cred-item:last-child {{
            border-bottom: none;
        }}
        .cred-val {{
            font-family: monospace;
            font-weight: 800;
            color: #60a5fa;
            font-size: 1.15rem;
            letter-spacing: 1px;
        }}
        .timer-val {{
            font-size: 2.2rem;
            font-weight: 900;
            color: #34d399;
            font-family: monospace;
            margin: 0.75rem 0 0.25rem;
        }}
        .alert {{
            padding: 0.9rem;
            border-radius: 0.75rem;
            margin-bottom: 1.25rem;
            font-size: 0.925rem;
            display: {alert_display};
        }}
        .alert.success {{
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid var(--success);
            color: #34d399;
        }}
        .alert.error {{
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid var(--error);
            color: #f87171;
        }}
        .manual-section {{
            margin-top: 1.5rem;
            padding-top: 1.25rem;
            border-top: 1px solid var(--border);
        }}
        .manual-toggle {{
            background: none;
            border: none;
            color: var(--text-muted);
            font-size: 0.85rem;
            cursor: pointer;
            text-decoration: underline;
        }}
        .manual-box {{
            display: none;
            margin-top: 1rem;
        }}
        .footer {{
            margin-top: 1.5rem;
            font-size: 0.8rem;
            color: #64748b;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon-circle">📶</div>
        <h1>{shop_name}</h1>
        <p class="subtitle">امسح الكود الثابت مرة واحدة، واحصل على حساب مؤقت خاص بك لتصفح الإنترنت فوراً.</p>

        <div class="alert {alert_type}">
            {alert_message}
        </div>

        <!-- Initial Request State -->
        <div id="initial-box" style="display: {init_display};">
            <form method="POST" action="/request-access">
                <button type="submit" class="btn-large">
                    <span>🚀</span> بدء الاتصال والحصول على كود خاص
                </button>
            </form>
            <p style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.75rem;">
                * سيتم تخصيص كود فريد لجهازك تلقائياً لمدة {duration_minutes} دقيقة.
            </p>
        </div>

        <!-- Credentials / Active Session State -->
        <div class="credentials-card">
            <div style="font-size: 1.75rem; margin-bottom: 0.25rem;">✅</div>
            <h3 style="color: #34d399; font-size: 1.15rem; margin-bottom: 0.75rem;">تم تفعيل الإنترنت لجهازك!</h3>

            <div class="cred-item">
                <span style="color: var(--text-muted);">اسم المستخدم الخاص بك:</span>
                <span class="cred-val">{username}</span>
            </div>
            <div class="cred-item">
                <span style="color: var(--text-muted);">كود الدخول المؤقت:</span>
                <span class="cred-val">{voucher_code}</span>
            </div>
            <div class="cred-item">
                <span style="color: var(--text-muted);">عنوان جهازك (IP):</span>
                <span class="cred-val" style="font-size: 0.9rem; color: #94a3b8;">{client_ip}</span>
            </div>

            <div style="margin-top: 1rem;">
                <p style="font-size: 0.85rem; color: var(--text-muted);">الوقت المتبقي لانتهاء صلاحية كودك:</p>
                <div class="timer-val" id="countdown-val">{remaining_minutes}:00</div>
            </div>
        </div>

        <!-- Optional Manual Voucher Section -->
        <div class="manual-section">
            <button class="manual-toggle" onclick="var el=document.getElementById('manual-box'); el.style.display = el.style.display==='block'?'none':'block';">
                لديك قسيمة مدفوعة أو كود مسبق الصنع؟ اضغط هنا
            </button>
            <div class="manual-box" id="manual-box">
                <form method="POST" action="/login">
                    <input type="text" name="code" placeholder="أدخل الكود اليدوي" style="width:100%; padding: 0.75rem; background:#0f172a; border: 1px solid var(--border); border-radius: 8px; color:#fff; text-align:center; font-weight:bold; margin-bottom: 0.5rem;" required>
                    <button type="submit" style="width:100%; padding: 0.75rem; background:#334155; color:#fff; border:none; border-radius:8px; cursor:pointer;">تفعيل الكود اليدوي</button>
                </form>
            </div>
        </div>

        <div class="footer">
            خدمة واي فاي آمنة للزبائن • {shop_name}
        </div>
    </div>
</body>
</html>
"""

class CaptivePortalHandler(http.server.BaseHTTPRequestHandler):
    voucher_mgr: Optional[VoucherManager] = None
    wifi_ctrl: Optional[WiFiController] = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 1. API: Real System Status
        if path == "/api/status":
            stats = self.voucher_mgr.get_stats() if self.voucher_mgr else {}
            wifi_status = self.wifi_ctrl.get_status() if self.wifi_ctrl else {}
            adapters = self.wifi_ctrl.detect_wifi_adapters() if self.wifi_ctrl else []
            adapter_info = adapters[0]["name"] if adapters else "غير متصل"
            is_running = wifi_status.get("is_running", False) and len(adapters) > 0

            data = {
                "hotspot_active": is_running,
                "ssid": config.get("hotspot_ssid", "Shop-Customer-WiFi"),
                "shop_name": config.get("shop_name", "WiFi Shop Manager"),
                "wall_duration": config.get("default_duration_minutes", 60),
                "adapter": adapter_info,
                "adapters_count": len(adapters),
                "ics_active": is_running,
                "stats": stats
            }
            self._send_json_response(data)
            return

        # 1b. API: Real Physical Hardware Scan
        if path == "/api/hardware/scan":
            adapters = self.wifi_ctrl.detect_wifi_adapters() if self.wifi_ctrl else []
            self._send_json_response({
                "connected": len(adapters) > 0,
                "adapters": adapters,
                "message": f"تم العثور على: {adapters[0]['name']}" if adapters else "لم يتم العثور على أي قطعة واي فاي في منافذ USB"
            })
            return

        # 2. API: Real Vouchers List from SQLite
        if path == "/api/vouchers":
            vouchers = self.voucher_mgr.get_all_vouchers(limit=100) if self.voucher_mgr else []
            self._send_json_response(vouchers)
            return

        # 3. API: Real Active Connected Clients
        if path == "/api/clients":
            active_sessions = self.voucher_mgr.get_active_sessions() if self.voucher_mgr else []
            self._send_json_response(active_sessions)
            return

        # 4. Static Files: index.css & index.js
        if path == "/index.css":
            css_path = BASE_DIR / "index.css"
            if css_path.exists():
                self._send_file_response(css_path, "text/css; charset=utf-8")
                return

        if path == "/index.js":
            js_path = BASE_DIR / "index.js"
            if js_path.exists():
                self._send_file_response(js_path, "application/javascript; charset=utf-8")
                return

        # 5. Admin Dashboard View
        if path in ("/admin", "/dashboard"):
            html_path = BASE_DIR / "index.html"
            if html_path.exists():
                self._send_file_response(html_path, "text/html; charset=utf-8")
                return

        # 6. Default Captive Portal Page for Guests
        shop_name = config.get("shop_name", "Shop WiFi")
        default_dur = config.get("default_duration_minutes", 60)
        client_ip = self.client_address[0]

        # Check if customer already has active session in SQLite
        sessions = self.voucher_mgr.get_active_sessions() if self.voucher_mgr else []
        active_for_client = next((s for s in sessions if s["client_ip"] == client_ip), None)

        if active_for_client:
            rem_mins = max(1, int((datetime.fromisoformat(active_for_client["expire_time"]) - datetime.now()).total_seconds() / 60))
            html = HTML_PAGE.format(
                shop_name=shop_name,
                duration_minutes=default_dur,
                alert_display="none",
                alert_type="",
                alert_message="",
                init_display="none",
                creds_display="block",
                username=f"GUEST-{active_for_client['voucher_code']}",
                voucher_code=active_for_client["voucher_code"],
                client_ip=client_ip,
                remaining_minutes=rem_mins
            )
        else:
            html = HTML_PAGE.format(
                shop_name=shop_name,
                duration_minutes=default_dur,
                alert_display="none",
                alert_type="",
                alert_message="",
                init_display="block",
                creds_display="none",
                username="----",
                voucher_code="----",
                client_ip=client_ip,
                remaining_minutes=default_dur
            )

        self._send_html_response(html)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        shop_name = config.get("shop_name", "Shop WiFi")
        default_dur = config.get("default_duration_minutes", 60)
        client_ip = self.client_address[0]

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else ""

        # 1. API: Create Voucher in SQLite
        if path == "/api/vouchers/create":
            try:
                body = json.loads(post_data) if post_data else {}
            except Exception:
                body = {}
            duration = int(body.get("duration", default_dur))
            price = float(body.get("price", 0.0))
            notes = str(body.get("notes", ""))

            voucher = self.voucher_mgr.create_voucher(duration_minutes=duration, price=price, notes=notes)
            self._send_json_response({"success": True, "voucher": voucher})
            return

        # 2. API: Revoke Voucher in SQLite
        if path == "/api/vouchers/revoke":
            try:
                body = json.loads(post_data) if post_data else {}
            except Exception:
                body = {}
            code = body.get("code", "")
            success = self.voucher_mgr.revoke_voucher(code)
            self._send_json_response({"success": success})
            return

        # 3. API: Toggle Hotspot
        if path == "/api/hotspot/toggle":
            status = self.wifi_ctrl.get_status()
            if status.get("is_running"):
                self.wifi_ctrl.stop_hotspot()
                self._send_json_response({"success": True, "active": False})
            else:
                s_ok, msg = self.wifi_ctrl.start_hotspot()
                self._send_json_response({"success": s_ok, "active": s_ok, "message": msg})
            return

        # 3b. API: Update Wi-Fi SSID Name & Settings
        if path == "/api/settings/update":
            try:
                body = json.loads(post_data) if post_data else {}
            except Exception:
                body = {}
            new_ssid = body.get("ssid", "").strip()
            new_pass = body.get("password", "").strip()
            new_shop = body.get("shop_name", "").strip()

            if new_ssid:
                config.set("hotspot_ssid", new_ssid)
            if new_pass:
                config.set("hotspot_password", new_pass)
            if new_shop:
                config.set("shop_name", new_shop)

            # Reconfigure hotspot driver with new SSID
            if self.wifi_ctrl and new_ssid:
                pwd = new_pass or config.get("hotspot_password", "ShopWiFiPassword123")
                self.wifi_ctrl.configure_hotspot(new_ssid, pwd)

            self._send_json_response({
                "success": True,
                "ssid": config.get("hotspot_ssid"),
                "shop_name": config.get("shop_name"),
                "message": f"تم تغيير اسم الواي فاي إلى: {config.get('hotspot_ssid')}"
            })
            return

        # 3c. API: Update Static Wall Poster Default Duration
        if path == "/api/settings/wall-duration":
            try:
                body = json.loads(post_data) if post_data else {}
            except Exception:
                body = {}
            new_dur = int(body.get("duration", 60))
            config.set("default_duration_minutes", new_dur)
            self._send_json_response({
                "success": True,
                "duration": new_dur,
                "message": f"تم ضبط مدة كود الحائط إلى {new_dur} دقيقة"
            })
            return

        # 3d. API: Manually Extend Time for an Active Client Session
        if path == "/api/sessions/extend":
            try:
                body = json.loads(post_data) if post_data else {}
            except Exception:
                body = {}
            code = body.get("code", "")
            minutes = int(body.get("minutes", 30))
            success, msg, data = self.voucher_mgr.extend_session(code, minutes)
            self._send_json_response({
                "success": success,
                "message": msg,
                "data": data
            })
            return

        # 4. Captive Portal: Auto-request access from wall QR
        if path == "/request-access":
            success, msg, data = self.voucher_mgr.generate_on_demand_guest_session(
                client_ip=client_ip,
                default_duration=default_dur
            )

            html = HTML_PAGE.format(
                shop_name=shop_name,
                duration_minutes=default_dur,
                alert_display="block",
                alert_type="success" if success else "error",
                alert_message=msg,
                init_display="none" if success else "block",
                creds_display="block" if success else "none",
                username=data.get("username", "GUEST"),
                voucher_code=data.get("code", "----"),
                client_ip=client_ip,
                remaining_minutes=data.get("remaining_minutes", default_dur)
            )
            self._send_html_response(html)
            return

        # 5. Captive Portal: Manual code submission
        if path == "/login":
            params = urllib.parse.parse_qs(post_data)
            code = params.get("code", [""])[0].strip().upper()

            success, msg, voucher = self.voucher_mgr.activate_voucher(code, client_ip)

            html = HTML_PAGE.format(
                shop_name=shop_name,
                duration_minutes=default_dur,
                alert_display="block",
                alert_type="success" if success else "error",
                alert_message=msg,
                init_display="none" if success else "block",
                creds_display="block" if success else "none",
                username=f"USER-{code}" if success else "----",
                voucher_code=code if success else "----",
                client_ip=client_ip,
                remaining_minutes=voucher.get("duration_minutes", default_dur) if voucher else default_dur
            )
            self._send_html_response(html)
            return

        self.send_response(404)
        self.end_headers()

    def _send_html_response(self, content: str):
        encoded = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json_response(self, data):
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_file_response(self, file_path: Path, content_type: str):
        with open(file_path, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        pass

class CaptiveServer:
    def __init__(self, voucher_mgr: VoucherManager, wifi_ctrl: Optional[WiFiController] = None, port: int = 8080):
        self.voucher_mgr = voucher_mgr
        self.wifi_ctrl = wifi_ctrl
        self.port = port
        self.server: Optional[socketserver.TCPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return

        CaptivePortalHandler.voucher_mgr = self.voucher_mgr
        CaptivePortalHandler.wifi_ctrl = self.wifi_ctrl

        socketserver.TCPServer.allow_reuse_address = True
        try:
            self.server = socketserver.TCPServer(("", self.port), CaptivePortalHandler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            print(f"[CaptiveServer] Server & API running at http://127.0.0.1:{self.port}/")
        except Exception as e:
            print(f"[CaptiveServer] Failed to bind to port {self.port}: {e}")

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
