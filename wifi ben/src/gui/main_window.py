"""
WiFi Shop Manager - Modern Desktop Graphical Interface (GUI).
Supports CustomTkinter with seamless fallback to standard Tkinter.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from datetime import datetime
from typing import Optional

from src.core.voucher_manager import VoucherManager
from src.core.wifi_controller import WiFiController
from src.core.captive_server import CaptiveServer
from src.utils.config import config

try:
    import customtkinter as ctk
    USE_CTK = True
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    BaseWindow = ctk.CTk
except ImportError:
    USE_CTK = False
    BaseWindow = tk.Tk

class MainWindow(BaseWindow):
    def __init__(self, voucher_mgr: VoucherManager, wifi_ctrl: WiFiController, server: CaptiveServer):
        super().__init__()

        self.voucher_mgr = voucher_mgr
        self.wifi_ctrl = wifi_ctrl
        self.server = server

        self.title("WiFi Shop Manager - مدير واي فاي المحل التجاري")
        self.geometry("980x680")
        self.minsize(850, 600)

        # State
        self.hotspot_active = False
        self.last_generated_code = ""

        self._build_ui()
        self._start_background_monitor()

    def _build_ui(self):
        if USE_CTK:
            self._build_ctk_ui()
        else:
            self._build_standard_tk_ui()

    def _build_ctk_ui(self):
        # Header Frame
        header = ctk.CTkFrame(self, corner_radius=10, height=70)
        header.pack(fill="x", padx=15, pady=10)

        title_lbl = ctk.CTkLabel(
            header,
            text="📶 WiFi Shop Manager | إدارة واي فاي المحل وقسائم الزبائن",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title_lbl.pack(side="left", padx=20, pady=15)

        self.status_badge = ctk.CTkLabel(
            header,
            text="● نقطة البث: متوقفة",
            text_color="#ef4444",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.status_badge.pack(side="right", padx=20)

        # Main Layout: 2 Columns
        main_content = ctk.CTkFrame(self, fg_color="transparent")
        main_content.pack(fill="both", expand=True, padx=15, pady=5)

        # Left Column: Generator & Hotspot Controls
        left_col = ctk.CTkFrame(main_content, width=420)
        left_col.pack(side="left", fill="both", padx=(0, 8), pady=5)

        # Hotspot Box
        hs_box = ctk.CTkFrame(left_col, corner_radius=8)
        hs_box.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(hs_box, text="⚙️ التحكم في بث الواي فاي (Hotspot)", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))
        
        # SSID Name Entry & Save Button
        ssid_frame = ctk.CTkFrame(hs_box, fg_color="transparent")
        ssid_frame.pack(fill="x", padx=12, pady=(2, 6))
        ctk.CTkLabel(ssid_frame, text="اسم شبكة الواي فاي للزبائن (SSID):", font=ctk.CTkFont(size=11), text_color="gray75").pack(anchor="w")

        ssid_row = ctk.CTkFrame(ssid_frame, fg_color="transparent")
        ssid_row.pack(fill="x", pady=(2, 0))

        self.ssid_entry = ctk.CTkEntry(ssid_row, placeholder_text="اسم الشبكة")
        self.ssid_entry.insert(0, config.get("hotspot_ssid", "Shop-Customer-WiFi"))
        self.ssid_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        btn_save_ssid = ctk.CTkButton(
            ssid_row,
            text="💾 حفظ",
            width=60,
            command=self._save_ssid
        )
        btn_save_ssid.pack(side="right")

        self.btn_toggle_hotspot = ctk.CTkButton(
            hs_box,
            text="تشغيل نقطة البث (Start Hotspot)",
            command=self._toggle_hotspot,
            fg_color="#10b981",
            hover_color="#059669"
        )
        self.btn_toggle_hotspot.pack(fill="x", padx=12, pady=(8, 6))

        # Static Wall Poster Button
        btn_wall_qr = ctk.CTkButton(
            hs_box,
            text="🖼️ ملصق الكود الثابت للحائط (Wall QR Poster)",
            command=self._open_wall_poster,
            fg_color="#4f46e5",
            hover_color="#4338ca"
        )
        btn_wall_qr.pack(fill="x", padx=12, pady=(0, 8))

        # Auto-Config Banner
        self.lbl_autoconfig = ctk.CTkLabel(
            hs_box,
            text="⚡ التكوين التلقائي (Auto-Config): يراقب منفذ USB لتفعيل البث و ICS فوراً",
            text_color="#38bdf8",
            font=ctk.CTkFont(size=11)
        )
        self.lbl_autoconfig.pack(padx=12, pady=(0, 10))

        # Voucher Generator Box
        gen_box = ctk.CTkFrame(left_col, corner_radius=8)
        gen_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        ctk.CTkLabel(gen_box, text="🎟️ توليد قسيمة جديدة (New Voucher)", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=12, pady=(12, 6))

        ctk.CTkLabel(gen_box, text="مدة الصلاحية:").pack(anchor="w", padx=12)
        self.duration_combo = ctk.CTkComboBox(
            gen_box,
            values=["15 دقيقة", "30 دقيقة", "1 ساعة (60 دقيقة)", "2 ساعة (120 دقيقة)", "3 ساعات (180 دقيقة)"],
            state="readonly"
        )
        self.duration_combo.set("1 ساعة (60 دقيقة)")
        self.duration_combo.pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkLabel(gen_box, text="ملاحظات / اسم الزبون (اختياري):").pack(anchor="w", padx=12)
        self.notes_entry = ctk.CTkEntry(gen_box, placeholder_text="مثال: طاولة 4 أو زبون VIP")
        self.notes_entry.pack(fill="x", padx=12, pady=(0, 12))

        btn_gen = ctk.CTkButton(
            gen_box,
            text="✨ توليد رمز القسيمة الآن",
            command=self._generate_voucher,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            height=38,
            font=ctk.CTkFont(weight="bold")
        )
        btn_gen.pack(fill="x", padx=12, pady=(0, 15))

        # Result display
        self.code_display_frame = ctk.CTkFrame(gen_box, corner_radius=8, fg_color="#0f172a")
        self.code_display_frame.pack(fill="x", padx=12, pady=(0, 10))

        self.lbl_code_result = ctk.CTkLabel(
            self.code_display_frame,
            text="----",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#60a5fa"
        )
        self.lbl_code_result.pack(pady=(12, 4))

        self.lbl_code_info = ctk.CTkLabel(
            self.code_display_frame,
            text="اضغط على زر التوليد لإنشاء رمز جديد",
            text_color="gray60",
            font=ctk.CTkFont(size=11)
        )
        self.lbl_code_info.pack(pady=(0, 8))

        btn_copy = ctk.CTkButton(
            self.code_display_frame,
            text="📋 نسخ الرمز",
            command=self._copy_code,
            width=120,
            height=28
        )
        btn_copy.pack(pady=(0, 12))

        # Right Column: Dashboard & Active Sessions
        right_col = ctk.CTkFrame(main_content)
        right_col.pack(side="right", fill="both", expand=True, padx=(8, 0), pady=5)

        # Stats Cards
        stats_frame = ctk.CTkFrame(right_col, fg_color="transparent")
        stats_frame.pack(fill="x", padx=10, pady=10)

        self.card_active = self._create_stat_card(stats_frame, "الجلسات النشطة", "0", "#10b981")
        self.card_total = self._create_stat_card(stats_frame, "إجمالي القسائم", "0", "#3b82f6")
        self.card_expired = self._create_stat_card(stats_frame, "منتهية الصلاحية", "0", "#64748b")

        # Active Clients Table
        ctk.CTkLabel(
            right_col,
            text="👥 الأجهزة المتصلة والجلسات النشطة حالياً",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=12, pady=(10, 4))

        # Scrollable Sessions Box
        self.sessions_scroll = ctk.CTkScrollableFrame(right_col, height=360)
        self.sessions_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._refresh_data()

    def _create_stat_card(self, parent, title, val, color):
        card = ctk.CTkFrame(parent, corner_radius=8)
        card.pack(side="left", fill="both", expand=True, padx=4)
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=11), text_color="gray70").pack(pady=(8, 0))
        lbl_val = ctk.CTkLabel(card, text=val, font=ctk.CTkFont(size=20, weight="bold"), text_color=color)
        lbl_val.pack(pady=(2, 8))
        return lbl_val

    def _build_standard_tk_ui(self):
        """Standard Tkinter UI fallback if CustomTkinter is not present."""
        self.configure(bg="#1e1e2e")
        lbl = tk.Label(
            self,
            text="📶 WiFi Shop Manager (Standard Tkinter Mode)",
            font=("Arial", 16, "bold"),
            bg="#1e1e2e",
            fg="white"
        )
        lbl.pack(pady=15)

        frame = tk.Frame(self, bg="#2a2a3e", padx=20, pady=20)
        frame.pack(fill="both", expand=True, padx=20, pady=10)

        btn = tk.Button(
            frame,
            text="توليد كود قسيمة عشوائي",
            command=self._generate_voucher,
            bg="#2563eb",
            fg="white",
            font=("Arial", 12, "bold")
        )
        btn.pack(pady=10)

        self.lbl_code_result = tk.Label(frame, text="----", font=("Arial", 22, "bold"), fg="#60a5fa", bg="#2a2a3e")
        self.lbl_code_result.pack(pady=10)

    def _open_wall_poster(self):
        """Displays instructions and generates the permanent wall QR poster with duration control."""
        from tkinter import simpledialog
        portal_ip = config.get("portal_ip", "192.168.137.1")
        portal_port = config.get("portal_port", 8080)
        portal_url = f"http://{portal_ip}:{portal_port}/"
        ssid = config.get("hotspot_ssid", "Shop-Customer-WiFi")
        current_dur = config.get("default_duration_minutes", 60)

        new_dur_str = simpledialog.askstring(
            "⏱️ مدة صلاحية ملصق الحائط",
            f"المدة التلقائية الممنوحة لكل زبون عند مسح كود الحائط (بالدقائق):\nالمدة الحالية: {current_dur} دقيقة.",
            initialvalue=str(current_dur)
        )
        if new_dur_str:
            try:
                new_dur = int(new_dur_str)
                if new_dur > 0:
                    config.set("default_duration_minutes", new_dur)
                    current_dur = new_dur
            except ValueError:
                pass

        info_msg = (
            f"🖼️ ملصق الكود الثابت للحائط (Static Wall QR Poster):\n\n"
            f"1. اطبع هذا الكود وقم بتعليقه على الحائط أو الطاولات.\n"
            f"2. اسم شبكة الواي فاي: {ssid}\n"
            f"3. الرابط الثابت: {portal_url}\n"
            f"4. مدة الصلاحية لكل زبون: {current_dur} دقيقة مجاناً.\n\n"
            f"عندما يمسح أي زبون هذا الكود، تفتح له البوابة التلقائية ويحصل فوراً على "
            f"اسم مستخدم وكلمة مرور مؤقتة خاصة به وحده!"
        )
        messagebox.showinfo("ملصق الحائط الدائم", info_msg)

    def _save_ssid(self):
        """Saves new Wi-Fi SSID name and reconfigures Windows hotspot driver."""
        new_ssid = self.ssid_entry.get().strip()
        if not new_ssid:
            messagebox.showwarning("تنبيه", "يرجى كتابة اسم لشبكة الواي فاي.")
            return
        config.set("hotspot_ssid", new_ssid)
        pwd = config.get("hotspot_password", "ShopWiFiPassword123")
        self.wifi_ctrl.configure_hotspot(new_ssid, pwd)
        messagebox.showinfo("تم الحفظ بنجاح", f"تم تحديث وتطبيق اسم شبكة الواي فاي للزبائن إلى:\n{new_ssid}")

    def _toggle_hotspot(self):
        if not self.hotspot_active:
            success, msg = self.wifi_ctrl.start_hotspot()
            if success:
                self.hotspot_active = True
                if USE_CTK:
                    self.status_badge.configure(text="● نقطة البث: نشطة", text_color="#10b981")
                    self.btn_toggle_hotspot.configure(
                        text="إيقاف نقطة البث (Stop Hotspot)",
                        fg_color="#ef4444",
                        hover_color="#dc2626"
                    )
                messagebox.showinfo("نقطة البث", "تم تشغيل بث شبكة الواي فاي بنجاح.")
            else:
                messagebox.showerror("فشل تشغيل البث", f"تعذر تشغيل نقطة البث:\n{msg}\nيرجى التأكد من تشغيل البرنامج بصلاحية المسؤول (Administrator).")
        else:
            self.wifi_ctrl.stop_hotspot()
            self.hotspot_active = False
            if USE_CTK:
                self.status_badge.configure(text="● نقطة البث: متوقفة", text_color="#ef4444")
                self.btn_toggle_hotspot.configure(
                    text="تشغيل نقطة البث (Start Hotspot)",
                    fg_color="#10b981",
                    hover_color="#059669"
                )
            messagebox.showinfo("نقطة البث", "تم إيقاف نقطة بث الواي فاي.")

    def _generate_voucher(self):
        durations = {
            "15 دقيقة": 15,
            "30 دقيقة": 30,
            "1 ساعة (60 دقيقة)": 60,
            "2 ساعة (120 دقيقة)": 120,
            "3 ساعات (180 دقيقة)": 180,
        }
        selected = self.duration_combo.get() if USE_CTK else "1 ساعة (60 دقيقة)"
        duration_mins = durations.get(selected, 60)
        notes = self.notes_entry.get().strip() if USE_CTK else ""

        voucher = self.voucher_mgr.create_voucher(duration_minutes=duration_mins, notes=notes)
        self.last_generated_code = voucher["code"]

        if USE_CTK:
            self.lbl_code_result.configure(text=voucher["code"])
            self.lbl_code_info.configure(text=f"صالحة لمدة {duration_mins} دقيقة • غير مستعملة")
            self.notes_entry.delete(0, "end")
        else:
            self.lbl_code_result.config(text=voucher["code"])

        self._refresh_data()

    def _copy_code(self):
        if self.last_generated_code:
            self.clipboard_clear()
            self.clipboard_append(self.last_generated_code)
            messagebox.showinfo("تم النسخ", f"تم نسخ الكود {self.last_generated_code} إلى الحافظة بنجاح.")

    def _revoke_session(self, code: str):
        if messagebox.askyesno("تأكيد الإلغاء", f"هل أنت متأكد من رغبتك في قطع الاتصال وإلغاء القسيمة {code}؟"):
            self.voucher_mgr.revoke_voucher(code)
            self._refresh_data()

    def _refresh_data(self):
        # Refresh statistics
        stats = self.voucher_mgr.get_stats()
        if USE_CTK:
            self.card_active.configure(text=str(stats["active_sessions"]))
            self.card_total.configure(text=str(stats["total_vouchers"]))
            self.card_expired.configure(text=str(stats["expired_vouchers"]))

            # Clear existing session items
            for widget in self.sessions_scroll.winfo_children():
                widget.destroy()

            sessions = self.voucher_mgr.get_active_sessions()
            if not sessions:
                lbl_empty = ctk.CTkLabel(
                    self.sessions_scroll,
                    text="لا يوجد أي زبائن متصلين حالياً بالإنترنت.",
                    text_color="gray60"
                )
                lbl_empty.pack(pady=30)
            else:
                for s in sessions:
                    self._render_session_row(s)

    def _render_session_row(self, s: dict):
        row = ctk.CTkFrame(self.sessions_scroll, corner_radius=6, fg_color="#1e293b")
        row.pack(fill="x", pady=4, padx=2)

        # Voucher Code & IP
        info_txt = f"رمز: {s['voucher_code']}  |  IP: {s['client_ip']}"
        lbl_info = ctk.CTkLabel(row, text=info_txt, font=ctk.CTkFont(weight="bold"))
        lbl_info.pack(side="left", padx=10, pady=8)

        # Remaining time
        expire_dt = datetime.fromisoformat(s["expire_time"])
        now = datetime.now()
        rem_mins = max(0, int((expire_dt - now).total_seconds() / 60))

        lbl_time = ctk.CTkLabel(
            row,
            text=f"الوقت المتبقي: {rem_mins} دقيقة",
            text_color="#34d399" if rem_mins > 10 else "#f87171"
        )
        lbl_time.pack(side="left", padx=15)

        # Action Buttons Frame
        actions_frame = ctk.CTkFrame(row, fg_color="transparent")
        actions_frame.pack(side="right", padx=10, pady=6)

        # Add Time Button
        btn_add_time = ctk.CTkButton(
            actions_frame,
            text="➕ إضافة وقت",
            width=90,
            height=26,
            fg_color="#10b981",
            hover_color="#059669",
            command=lambda c=s["voucher_code"]: self._prompt_add_time(c)
        )
        btn_add_time.pack(side="left", padx=(0, 6))

        # Revoke Button
        btn_revoke = ctk.CTkButton(
            actions_frame,
            text="قطع الاتصال",
            width=80,
            height=26,
            fg_color="#ef4444",
            hover_color="#dc2626",
            command=lambda c=s["voucher_code"]: self._revoke_session(c)
        )
        btn_revoke.pack(side="left")

    def _prompt_add_time(self, code: str):
        """Prompt to manually extend an active customer session."""
        from tkinter import simpledialog
        mins_str = simpledialog.askstring(
            "إضافة وقت إضافي للزبون",
            f"كم عدد الدقائق الإضافية التي تريد إضافتها للزبون صاحب القسيمة ({code})؟\n(مثال: 15، 30، 60 دقيقة):",
            initialvalue="30"
        )
        if mins_str:
            try:
                mins = int(mins_str)
                if mins <= 0:
                    raise ValueError()
                success, msg, data = self.voucher_mgr.extend_session(code, mins)
                if success:
                    rem = data.get("remaining_minutes", mins) if data else mins
                    messagebox.showinfo("تم تمديد الوقت بنجاح", f"تمت إضافة {mins} دقيقة إضافية للزبون ({code})!\nالوقت المتبقي الإجمالي: {rem} دقيقة.")
                    self._refresh_data()
                else:
                    messagebox.showwarning("تنبيه", msg)
            except ValueError:
                messagebox.showerror("خطأ", "يرجى كتابة عدد دقائق صحيح (رقم أكبر من صفر).")

    def _start_background_monitor(self):
        """Monitors voucher expirations and refreshes GUI every 5 seconds."""
        def monitor_loop():
            while True:
                time.sleep(5)
                try:
                    expired = self.voucher_mgr.check_and_expire_sessions()
                    if expired:
                        print(f"[Monitor] Expired {len(expired)} session(s).")
                    self.after(0, self._refresh_data)
                except Exception as e:
                    print(f"[Monitor Error] {e}")

        t = threading.Thread(target=monitor_loop, daemon=True)
        t.start()
