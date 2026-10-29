"""
Voucher Manager: Handles generation, SQLite persistence, activation,
and expiration tracking for Wi-Fi guest access codes.
"""
import sqlite3
import random
import string
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from src.utils.config import DB_PATH

class VoucherManager:
    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes the database schema if not present."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Vouchers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vouchers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    duration_minutes INTEGER NOT NULL,
                    price REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'PENDING',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    activated_at TIMESTAMP,
                    expires_at TIMESTAMP,
                    client_ip TEXT,
                    client_mac TEXT,
                    notes TEXT
                )
            """)

            # Active Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    voucher_code TEXT NOT NULL,
                    client_ip TEXT NOT NULL,
                    client_mac TEXT,
                    start_time TIMESTAMP NOT NULL,
                    expire_time TIMESTAMP NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (voucher_code) REFERENCES vouchers(code)
                )
            """)

            conn.commit()

    @staticmethod
    def generate_random_code(length: int = 6) -> str:
        """Generates a clean, readable alphanumeric code (no confusing chars like 0/O, 1/I)."""
        chars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
        return "".join(random.choice(chars) for _ in range(length))

    def create_voucher(self, duration_minutes: int, price: float = 0.0, notes: str = "") -> Dict:
        """Creates a single new voucher and stores it in the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            while True:
                code = self.generate_random_code(6)
                cursor.execute("SELECT id FROM vouchers WHERE code = ?", (code,))
                if not cursor.fetchone():
                    break

            cursor.execute("""
                INSERT INTO vouchers (code, duration_minutes, price, status, notes)
                VALUES (?, ?, ?, 'PENDING', ?)
            """, (code, duration_minutes, price, notes))
            conn.commit()

            return {
                "code": code,
                "duration_minutes": duration_minutes,
                "price": price,
                "status": "PENDING",
                "notes": notes
            }

    def generate_on_demand_guest_session(self, client_ip: str, client_mac: str = "", default_duration: int = 60, user_agent: str = "") -> Tuple[bool, str, Dict]:
        """
        Triggered when a customer scans the STATIC WALL QR CODE and taps 'Get Internet Access'.
        Automatically generates a unique username and temporary password/code for this customer,
        activates their session immediately, and starts their personal countdown.
        """
        now = datetime.now()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Check if this IP or MAC already has an active valid session
            cursor.execute("""
                SELECT s.*, v.duration_minutes, v.status, v.expires_at, v.notes
                FROM active_sessions s
                JOIN vouchers v ON s.voucher_code = v.code
                WHERE s.is_active = 1 AND (s.client_ip = ? OR (s.client_mac != '' AND s.client_mac = ?))
                ORDER BY s.expire_time DESC LIMIT 1
            """, (client_ip, client_mac))
            existing = cursor.fetchone()

            if existing:
                expires_at = datetime.fromisoformat(existing["expire_time"])
                if now < expires_at:
                    rem_mins = max(1, int((expires_at - now).total_seconds() / 60))
                    return True, f"لديك جلسة نشطة بالفعل! الوقت المتبقي: {rem_mins} دقيقة.", {
                        "username": f"User-{existing['voucher_code']}",
                        "code": existing["voucher_code"],
                        "duration_minutes": existing["duration_minutes"],
                        "remaining_minutes": rem_mins,
                        "status": "ACTIVE",
                        "expires_at": existing["expire_time"],
                        "client_ip": client_ip
                    }
                else:
                    # Expire old session
                    cursor.execute("UPDATE active_sessions SET is_active = 0 WHERE id = ?", (existing["id"],))
                    cursor.execute("UPDATE vouchers SET status = 'EXPIRED' WHERE code = ?", (existing["voucher_code"],))
                    conn.commit()

            # 2. Generate a brand new UNIQUE guest code & username for this customer
            while True:
                code = self.generate_random_code(6)
                cursor.execute("SELECT id FROM vouchers WHERE code = ?", (code,))
                if not cursor.fetchone():
                    break

            username = f"GUEST-{code}"
            expires_at = now + timedelta(minutes=default_duration)

            cursor.execute("""
                INSERT INTO vouchers (code, duration_minutes, price, status, created_at, activated_at, expires_at, client_ip, client_mac, notes)
                VALUES (?, ?, 0.0, 'ACTIVE', ?, ?, ?, ?, ?, ?)
            """, (code, default_duration, now.isoformat(), now.isoformat(), expires_at.isoformat(), client_ip, client_mac, f"توليد ذاتي (Wall QR) - {username}"))

            cursor.execute("""
                INSERT INTO active_sessions (voucher_code, client_ip, client_mac, start_time, expire_time, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (code, client_ip, client_mac, now.isoformat(), expires_at.isoformat()))

            conn.commit()

            return True, f"تم تفعيل الإنترنت لك بنجاح! متاح لك {default_duration} دقيقة.", {
                "username": username,
                "code": code,
                "duration_minutes": default_duration,
                "remaining_minutes": default_duration,
                "status": "ACTIVE",
                "expires_at": expires_at.isoformat(),
                "client_ip": client_ip
            }

    def batch_create_vouchers(self, count: int, duration_minutes: int, price: float = 0.0) -> List[Dict]:
        """Creates multiple vouchers in a single transaction."""
        created = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for _ in range(count):
                while True:
                    code = self.generate_random_code(6)
                    cursor.execute("SELECT id FROM vouchers WHERE code = ?", (code,))
                    if not cursor.fetchone():
                        break

                cursor.execute("""
                    INSERT INTO vouchers (code, duration_minutes, price, status)
                    VALUES (?, ?, ?, 'PENDING')
                """, (code, duration_minutes, price))
                created.append({
                    "code": code,
                    "duration_minutes": duration_minutes,
                    "price": price,
                    "status": "PENDING"
                })
            conn.commit()
        return created

    def activate_voucher(self, code: str, client_ip: str, client_mac: str = "") -> Tuple[bool, str, Optional[Dict]]:
        """
        Activates a voucher code when entered by a customer via the captive portal.
        Returns: (success: bool, message: str, voucher_data: dict)
        """
        code = code.strip().upper()
        now = datetime.now()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vouchers WHERE code = ?", (code,))
            row = cursor.fetchone()

            if not row:
                return False, "رمز القسيمة غير صحيح. يرجى التحقق من الكود.", None

            voucher = dict(row)

            # Check if already active
            if voucher["status"] == "ACTIVE":
                # Check if it is still within expiration window
                expires_at = datetime.fromisoformat(voucher["expires_at"])
                if now < expires_at:
                    remaining_mins = int((expires_at - now).total_seconds() / 60)
                    return True, f"القسيمة نشطة بالفعل. الوقت المتبقي: {remaining_mins} دقيقة.", voucher
                else:
                    self._mark_expired(conn, code)
                    return False, "انتهت صلاحية هذه القسيمة.", None

            if voucher["status"] in ("EXPIRED", "REVOKED"):
                return False, "هذه القسيمة مستعملة أو منتهية الصلاحية.", None

            # Activate pending voucher
            duration = voucher["duration_minutes"]
            expires_at = now + timedelta(minutes=duration)

            cursor.execute("""
                UPDATE vouchers
                SET status = 'ACTIVE',
                    activated_at = ?,
                    expires_at = ?,
                    client_ip = ?,
                    client_mac = ?
                WHERE code = ?
            """, (now.isoformat(), expires_at.isoformat(), client_ip, client_mac, code))

            cursor.execute("""
                INSERT INTO active_sessions (voucher_code, client_ip, client_mac, start_time, expire_time, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (code, client_ip, client_mac, now.isoformat(), expires_at.isoformat()))

            conn.commit()

            voucher.update({
                "status": "ACTIVE",
                "activated_at": now.isoformat(),
                "expires_at": expires_at.isoformat(),
                "client_ip": client_ip,
                "client_mac": client_mac
            })

            return True, f"تم التفعيل بنجاح! متاح لك {duration} دقيقة من الإنترنت.", voucher

    def check_and_expire_sessions(self) -> List[Dict]:
        """
        Runs periodically to mark expired vouchers and deactivate sessions.
        Returns a list of sessions that were newly expired.
        """
        now = datetime.now().isoformat()
        expired_sessions = []

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.*, v.notes
                FROM active_sessions s
                JOIN vouchers v ON s.voucher_code = v.code
                WHERE s.is_active = 1 AND s.expire_time <= ?
            """, (now,))
            rows = cursor.fetchall()

            for row in rows:
                item = dict(row)
                expired_sessions.append(item)
                # Mark session inactive
                cursor.execute("UPDATE active_sessions SET is_active = 0 WHERE id = ?", (item["id"],))
                # Mark voucher expired
                cursor.execute("UPDATE vouchers SET status = 'EXPIRED' WHERE code = ?", (item["voucher_code"],))

            if expired_sessions:
                conn.commit()

        return expired_sessions

    def revoke_voucher(self, code: str) -> bool:
        """Manually revokes an active or pending voucher."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE vouchers SET status = 'REVOKED' WHERE code = ?", (code,))
            cursor.execute("UPDATE active_sessions SET is_active = 0 WHERE voucher_code = ?", (code,))
            conn.commit()
            return cursor.rowcount > 0

    def extend_session(self, code: str, additional_minutes: int = 30) -> Tuple[bool, str, Optional[Dict]]:
        """
        Manually extends time for an active customer session.
        Increases duration and pushes expire_time further by additional_minutes.
        """
        code = code.strip().upper()
        now = datetime.now()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.*, v.duration_minutes
                FROM active_sessions s
                JOIN vouchers v ON s.voucher_code = v.code
                WHERE s.voucher_code = ? AND s.is_active = 1
                ORDER BY s.id DESC LIMIT 1
            """, (code,))
            row = cursor.fetchone()

            if not row:
                return False, "لم يتم العثور على جلسة نشطة لهذه القسيمة.", None

            session = dict(row)
            current_expire = datetime.fromisoformat(session["expire_time"])

            # If already past, extend from now; otherwise add to current expire time
            base_time = current_expire if current_expire > now else now
            new_expire = base_time + timedelta(minutes=additional_minutes)
            new_duration = session["duration_minutes"] + additional_minutes

            cursor.execute("""
                UPDATE active_sessions
                SET expire_time = ?
                WHERE id = ?
            """, (new_expire.isoformat(), session["id"]))

            cursor.execute("""
                UPDATE vouchers
                SET expires_at = ?,
                    duration_minutes = ?,
                    status = 'ACTIVE'
                WHERE code = ?
            """, (new_expire.isoformat(), new_duration, code))

            conn.commit()

            rem_mins = max(1, int((new_expire - now).total_seconds() / 60))
            return True, f"تمت إضافة {additional_minutes} دقيقة بنجاح! الوقت المتبقي: {rem_mins} دقيقة.", {
                "code": code,
                "added_minutes": additional_minutes,
                "new_duration": new_duration,
                "expire_time": new_expire.isoformat(),
                "remaining_minutes": rem_mins
            }

    def get_active_sessions(self) -> List[Dict]:
        """Returns all currently active connected sessions."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.id, s.voucher_code, s.client_ip, s.client_mac, s.start_time, s.expire_time,
                       v.duration_minutes, v.notes
                FROM active_sessions s
                JOIN vouchers v ON s.voucher_code = v.code
                WHERE s.is_active = 1 AND s.expire_time > ?
                ORDER BY s.expire_time ASC
            """, (now,))
            return [dict(row) for row in cursor.fetchall()]

    def get_all_vouchers(self, limit: int = 100) -> List[Dict]:
        """Returns a list of vouchers sorted by creation date."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM vouchers ORDER BY id DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> Dict:
        """Returns statistical metrics for the dashboard."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM vouchers")
            total = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM vouchers WHERE status = 'ACTIVE'")
            active = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM vouchers WHERE status = 'PENDING'")
            pending = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM vouchers WHERE status = 'EXPIRED'")
            expired = cursor.fetchone()[0]

            cursor.execute("SELECT COALESCE(SUM(price), 0.0) FROM vouchers WHERE status IN ('ACTIVE', 'EXPIRED')")
            revenue = cursor.fetchone()[0]

            return {
                "total_vouchers": total,
                "active_sessions": active,
                "pending_vouchers": pending,
                "expired_vouchers": expired,
                "total_revenue": revenue,
            }

    def _mark_expired(self, conn: sqlite3.Connection, code: str):
        cursor = conn.cursor()
        cursor.execute("UPDATE vouchers SET status = 'EXPIRED' WHERE code = ?", (code,))
        cursor.execute("UPDATE active_sessions SET is_active = 0 WHERE voucher_code = ?", (code,))
        conn.commit()
