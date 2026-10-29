"""
Configuration Manager for WiFi Shop Manager v2
Handles persistent settings (Shop name, SSID, Wall poster duration, Port) in a local config.json file.
Runs without requiring any Administrator privileges.
"""
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config.json"

DEFAULT_CONFIG = {
    "shop_name": "WiFi Shop Manager",
    "hotspot_ssid": "Shop-Customer-WiFi",
    "default_duration_minutes": 60,
    "portal_port": 8080,
    "auto_open_browser": True
}

class Config:
    def __init__(self):
        self._config = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._config.update(data)
            except Exception as e:
                print(f"[Config Warning] Could not parse config.json, using defaults: {e}")
        else:
            self.save()

    def save(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Config Warning] Could not save config.json: {e}")

    def get(self, key, default=None):
        return self._config.get(key, default)

    def set(self, key, value):
        self._config[key] = value
        self.save()

    def to_dict(self):
        return self._config.copy()

config = Config()
