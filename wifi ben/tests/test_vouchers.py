"""
Unit tests for VoucherManager logic.
"""
import unittest
import tempfile
import os
from datetime import datetime, timedelta
from src.core.voucher_manager import VoucherManager

class TestVoucherManager(unittest.TestCase):
    def setUp(self):
        # Use a temporary SQLite database for testing
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.mgr = VoucherManager(db_path=self.temp_db.name)

    def tearDown(self):
        if os.path.exists(self.temp_db.name):
            os.remove(self.temp_db.name)

    def test_create_voucher(self):
        voucher = self.mgr.create_voucher(duration_minutes=30, price=5.0, notes="Table 1")
        self.assertIsNotNone(voucher["code"])
        self.assertEqual(len(voucher["code"]), 6)
        self.assertEqual(voucher["duration_minutes"], 30)
        self.assertEqual(voucher["status"], "PENDING")

    def test_activate_voucher(self):
        voucher = self.mgr.create_voucher(duration_minutes=60)
        code = voucher["code"]

        success, msg, data = self.mgr.activate_voucher(code, client_ip="192.168.137.50")
        self.assertTrue(success)
        self.assertEqual(data["status"], "ACTIVE")
        self.assertEqual(data["client_ip"], "192.168.137.50")

    def test_activate_invalid_code(self):
        success, msg, data = self.mgr.activate_voucher("INVALID_CODE", client_ip="192.168.137.50")
        self.assertFalse(success)
        self.assertIsNone(data)

    def test_revoke_voucher(self):
        voucher = self.mgr.create_voucher(duration_minutes=15)
        code = voucher["code"]
        self.mgr.activate_voucher(code, client_ip="192.168.137.20")

        revoked = self.mgr.revoke_voucher(code)
        self.assertTrue(revoked)

        all_vouchers = self.mgr.get_all_vouchers()
        self.assertEqual(all_vouchers[0]["status"], "REVOKED")

    def test_on_demand_guest_session(self):
        # Customer 1 scans wall QR
        success, msg, data1 = self.mgr.generate_on_demand_guest_session(client_ip="192.168.137.55", default_duration=60)
        self.assertTrue(success)
        self.assertTrue(data1["username"].startswith("GUEST-"))

        # Customer 2 scans wall QR -> gets a completely DIFFERENT code
        success2, msg2, data2 = self.mgr.generate_on_demand_guest_session(client_ip="192.168.137.56", default_duration=60)
        self.assertTrue(success2)
        self.assertNotEqual(data1["code"], data2["code"])
        self.assertNotEqual(data1["username"], data2["username"])

    def test_extend_session(self):
        voucher = self.mgr.create_voucher(duration_minutes=30)
        code = voucher["code"]
        self.mgr.activate_voucher(code, client_ip="192.168.137.99")

        success, msg, data = self.mgr.extend_session(code, additional_minutes=15)
        self.assertTrue(success)
        self.assertEqual(data["new_duration"], 45)
        self.assertEqual(data["added_minutes"], 15)

if __name__ == "__main__":
    unittest.main()

