"""
WiFi Shop Manager - Main Application Entrypoint
"""
import sys
import os
import ctypes
import platform

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.voucher_manager import VoucherManager
from src.core.wifi_controller import WiFiController
from src.core.captive_server import CaptiveServer
from src.gui.main_window import MainWindow
from src.utils.config import config

def is_admin() -> bool:
    """Checks whether the script is currently running with Windows Administrator rights."""
    if platform.system().lower() != "windows":
        return True
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def enable_high_dpi_awareness():
    """Enhances text sharpness on modern Windows 10/11 high-DPI displays."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

def main():
    enable_high_dpi_awareness()

    print("==================================================")
    print("      📶 WiFi Shop Manager - System Startup       ")
    print("==================================================")

    if not is_admin():
        print("[WARNING] The application is NOT running as Administrator.")
        print("          Some Wi-Fi hotspot features might require elevated privileges.")
    else:
        print("[OK] Running with Administrator privileges.")

    # 1. Initialize Core Managers
    voucher_mgr = VoucherManager()
    wifi_ctrl = WiFiController()

    # 2. Automated Wi-Fi USB Dongle Detection & ICS Provisioning
    ssid = config.get("hotspot_ssid", "Shop-Customer-WiFi")
    password = config.get("hotspot_password", "ShopWiFiPassword123")

    print("[AutoConfig] Starting USB Wi-Fi dongle watcher & ICS auto-provisioning daemon...")
    wifi_ctrl.start_dongle_auto_watcher(ssid=ssid, password=password)

    # 3. Start Built-in Captive Portal & REST API Server
    portal_port = config.get("portal_port", 8080)
    server = CaptiveServer(voucher_mgr=voucher_mgr, wifi_ctrl=wifi_ctrl, port=portal_port)
    server.start()

    # 4. Launch Desktop GUI
    app = MainWindow(voucher_mgr=voucher_mgr, wifi_ctrl=wifi_ctrl, server=server)

    try:
        app.mainloop()
    finally:
        print("[Shutdown] Cleaning up background services...")
        server.stop()
        print("[Shutdown] Application closed safely.")

if __name__ == "__main__":
    main()
