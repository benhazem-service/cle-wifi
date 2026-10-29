"""
Voucher & Guest Session Manager for WiFi Shop Manager v2
Pure Python + SQLite. Runs with standard user privileges (Zero Administrator / UAC requirement).
"""
import sqlite3
import random
import string
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "vouchers_v2.db"

class VoucherManager:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(DB_PATH)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Creates the vouchers and sessions table with proper indexes."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vouchers (
                    code TEXT PRIMARY KEY,
                    username TEXT,
                    duration_minutes INTEGER NOT NULL,
                    price REAL DEFAULT 0.0,
                    status TEXT NOT NULL,  -- PENDING, ACTIVE, EXPIRED, REVOKED
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    client_ip TEXT,
                    client_mac TEXT,
                    notes TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vouchers_status ON vouchers (status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vouchers_ip ON vouchers (client_ip)")
            conn.commit()

    @staticmethod
    def generate_code(length: int = 6) -> str:
        """Generates a secure, human-friendly voucher code excluding ambiguous characters (0, O, 1, I)."""
        chars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
        suffix = "".join(random.choice(chars) for _ in range(length))
        return f"WIFI-{suffix}"

    def create_voucher(self, duration_minutes: int = 60, price: float = 0.0, notes: str = "") -> Dict[str, Any]:
        """Creates a new ready-to-use voucher."""
        code = self.generate_code()
        username = f"GUEST-{code}"
        now_str = datetime.now().isoformat()

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO vouchers (code, username, duration_minutes, price, status, created_at, notes)
                VALUES (?, ?, ?, ?, 'PENDING', ?, ?)
            """, (code, username, duration_minutes, price, now_str, notes))
            conn.commit()

        return {
            "code": code,
            "username": username,
            "duration_minutes": duration_minutes,
            "price": price,
            "status": "PENDING",
            "created_at": now_str,
            "notes": notes
        }

    def activate_voucher(self, code: str, client_ip: str = "192.168.137.2", client_mac: str = "جهاز متصل") -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Activates a voucher when a customer enters it in the portal."""
        self.check_and_expire_sessions()

        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM vouchers WHERE code = ?", (code,))
            row = cursor.fetchone()

            if not row:
                return False, "رمز القسيمة غير صحيح. يرجى التأكد من الرمز والمحاولة مجدداً.", None

            voucher = dict(row)

            if voucher["status"] == "REVOKED":
                return False, "تم إلغاء صلاحية هذه القسيمة من قبل إدارة المحل.", None

            if voucher["status"] == "EXPIRED":
                return False, "انتهت مدة صلاحية هذه القسيمة.", None

            now = datetime.now()
            if voucher["status"] == "ACTIVE":
                # Already active, return existing remaining time
                expire_dt = datetime.fromisoformat(voucher["expires_at"])
                rem_mins = max(1, int((expire_dt - now).total_seconds() / 60))
                return True, "القسيمة نشطة بالفعل لجهازك.", {
                    "code": voucher["code"],
                    "username": voucher["username"],
                    "remaining_minutes": rem_mins,
                    "status": "ACTIVE",
                    "expires_at": voucher["expires_at"]
                }

            # First-time activation
            duration = voucher["duration_minutes"]
            expires_at = (now + timedelta(minutes=duration)).isoformat()

            conn.execute("""
                UPDATE vouchers
                SET status = 'ACTIVE', expires_at = ?, client_ip = ?, client_mac = ?
                WHERE code = ?
            """, (expires_at, client_ip, client_mac, code))
            conn.commit()

            return True, "تم تفعيل القسيمة بنجاح! الإنترنت متصل الآن.", {
                "code": code,
                "username": voucher["username"],
                "remaining_minutes": duration,
                "status": "ACTIVE",
                "expires_at": expires_at,
                "client_ip": client_ip
            }

    def generate_on_demand_guest_session(self, client_ip: str, default_duration: int = 60) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Called when a guest scans the static Wall Poster QR code.
        Generates a unique temporary credential automatically without shop owner intervention.
        """
        self.check_and_expire_sessions()

        with self._get_connection() as conn:
            # Check if this client IP already has an active session
            cursor = conn.execute("""
                SELECT * FROM vouchers
                WHERE client_ip = ? AND status = 'ACTIVE' AND expires_at > ?
                ORDER BY expires_at DESC LIMIT 1
            """, (client_ip, datetime.now().isoformat()))
            row = cursor.fetchone()

            if row:
                voucher = dict(row)
                rem_mins = max(1, int((datetime.fromisoformat(voucher["expires_at"]) - datetime.now()).total_seconds() / 60))
                return True, "أهلاً بك مجدداً! جهازك متصل بالفعل.", {
                    "code": voucher["code"],
                    "username": voucher["username"],
                    "duration_minutes": voucher["duration_minutes"],
                    "remaining_minutes": rem_mins,
                    "status": "ACTIVE",
                    "expires_at": voucher["expires_at"],
                    "is_new": False
                }

            # Generate fresh unique session for this guest
            code = self.generate_code()
            username = f"GUEST-{code}"
            now = datetime.now()
            expires_at = (now + timedelta(minutes=default_duration)).isoformat()

            conn.execute("""
                INSERT INTO vouchers (code, username, duration_minutes, price, status, created_at, expires_at, client_ip, client_mac, notes)
                VALUES (?, ?, ?, 0.0, 'ACTIVE', ?, ?, ?, 'طلب ذاتي (Wall QR)', 'كود ذاتي لزبون ملصق الحائط')
            """, (code, username, default_duration, now.isoformat(), expires_at, client_ip))
            conn.commit()

            return True, "تم توليد حسابك الخاص وتفعيل الإنترنت بنجاح!", {
                "code": code,
                "username": username,
                "duration_minutes": default_duration,
                "remaining_minutes": default_duration,
                "status": "ACTIVE",
                "expires_at": expires_at,
                "is_new": True
            }

    def extend_session(self, code: str, additional_minutes: int) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Manually adds extra time to an active client session from the shop owner dashboard.
        Calculates new expiry based on max(current_expiry, now) + additional_minutes.
        """
        if additional_minutes <= 0:
            return False, "يجب أن تكون المدة الإضافية أكبر من الصفر.", None

        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM vouchers WHERE code = ?", (code,))
            row = cursor.fetchone()

            if not row:
                return False, f"لم يتم العثور على القسيمة ذات الرمز {code}.", None

            voucher = dict(row)
            now = datetime.now()
            base_time = now

            if voucher["expires_at"]:
                try:
                    cur_exp = datetime.fromisoformat(voucher["expires_at"])
                    if cur_exp > now:
                        base_time = cur_exp
                except Exception:
                    base_time = now

            new_expires = base_time + timedelta(minutes=additional_minutes)
            new_expires_str = new_expires.isoformat()
            new_duration = (voucher["duration_minutes"] or 0) + additional_minutes

            conn.execute("""
                UPDATE vouchers
                SET status = 'ACTIVE', expires_at = ?, duration_minutes = ?
                WHERE code = ?
            """, (new_expires_str, new_duration, code))
            conn.commit()

            rem_mins = max(1, int((new_expires - now).total_seconds() / 60))
            return True, f"تمت إضافة {additional_minutes} دقيقة إضافية بنجاح للزبون ({code})!", {
                "code": code,
                "added_minutes": additional_minutes,
                "remaining_minutes": rem_mins,
                "new_duration": new_duration,
                "expires_at": new_expires_str
            }

    def revoke_voucher(self, code: str) -> bool:
        """Revokes a voucher immediately."""
        with self._get_connection() as conn:
            cursor = conn.execute("UPDATE vouchers SET status = 'REVOKED' WHERE code = ?", (code,))
            conn.commit()
            return cursor.rowcount > 0

    def check_and_expire_sessions(self) -> List[str]:
        """Automatically checks and marks expired sessions."""
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT code FROM vouchers
                WHERE status = 'ACTIVE' AND expires_at IS NOT NULL AND expires_at <= ?
            """, (now_str,))
            expired_codes = [r["code"] for r in cursor.fetchall()]

            if expired_codes:
                conn.execute("""
                    UPDATE vouchers
                    SET status = 'EXPIRED'
                    WHERE status = 'ACTIVE' AND expires_at IS NOT NULL AND expires_at <= ?
                """, (now_str,))
                conn.commit()

            return expired_codes

    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Returns all currently active connected sessions."""
        self.check_and_expire_sessions()
        now = datetime.now()

        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM vouchers
                WHERE status = 'ACTIVE' AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY expires_at ASC
            """, (now.isoformat(),))

            results = []
            for row in cursor.fetchall():
                v = dict(row)
                rem_mins = 0
                if v["expires_at"]:
                    rem_mins = max(1, int((datetime.fromisoformat(v["expires_at"]) - now).total_seconds() / 60))

                results.append({
                    "voucher_code": v["code"],
                    "username": v["username"],
                    "client_ip": v["client_ip"] or "192.168.137.2",
                    "client_mac": v["client_mac"] or "جهاز متصل",
                    "duration_minutes": v["duration_minutes"],
                    "remaining_minutes": rem_mins,
                    "expire_time": v["expires_at"],
                    "notes": v["notes"] or ""
                })
            return results

    def get_all_vouchers(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Returns voucher history."""
        self.check_and_expire_sessions()
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM vouchers ORDER BY rowid DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def get_stats(self) -> Dict[str, Any]:
        """Calculates live analytics."""
        self.check_and_expire_sessions()
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cur_active = conn.execute("SELECT COUNT(*) FROM vouchers WHERE status = 'ACTIVE' AND (expires_at IS NULL OR expires_at > ?)", (now_str,)).fetchone()[0]
            cur_total = conn.execute("SELECT COUNT(*) FROM vouchers").fetchone()[0]
            cur_expired = conn.execute("SELECT COUNT(*) FROM vouchers WHERE status = 'EXPIRED'").fetchone()[0]
            cur_rev = conn.execute("SELECT SUM(price) FROM vouchers").fetchone()[0] or 0.0

            return {
                "active_sessions": cur_active,
                "total_vouchers": cur_total,
                "expired_vouchers": cur_expired,
                "revenue": round(cur_rev, 2)
            }

    def clear_all(self):
        """Clears all records."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM vouchers")
            conn.commit()
