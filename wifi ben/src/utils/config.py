"""
Configuration settings and state management for WiFi Shop Manager.
"""
import os
import json
from pathlib import Path

# Paths configuration
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "src" / "assets"
CONFIG_FILE = DATA_DIR / "config.json"
DB_PATH = DATA_DIR / "shop_wifi.db"

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

DEFAULT_CONFIG = {
    "shop_name": "My Shop WiFi",
    "hotspot_ssid": "Shop-Customer-WiFi",
    "hotspot_password": "ShopWiFiPassword123",
    "portal_port": 8080,
    "default_duration_minutes": 60,
    "portal_ip": "192.168.137.1",
    "auto_refresh_interval_sec": 5,
    "currency": "MAD",
}

class Config:
    def __init__(self):
        self.data = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.data.update(saved)
            except Exception as e:
                print(f"[Config] Error loading config: {e}")

    def save(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Config] Error saving config: {e}")

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

# Global config singleton
config = Config()
