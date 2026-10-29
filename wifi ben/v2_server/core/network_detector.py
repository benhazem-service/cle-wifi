"""
Network Detector for WiFi Shop Manager v2
Detects local IP address and Windows Mobile Hotspot interface without requiring Administrator privileges.
"""
import socket
import subprocess
from typing import List, Dict, Optional, Any

def get_local_ip_addresses() -> List[str]:
    """Retrieves all local IPv4 addresses assigned to the PC without requiring Administrator rights."""
    ips = []
    try:
        # 1. Primary socket connect check (returns active LAN/Wi-Fi IP)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Does not actually connect externally, just determines routing interface
            s.connect(("8.8.8.8", 80))
            primary_ip = s.getsockname()[0]
            if primary_ip and primary_ip not in ips and not primary_ip.startswith("127."):
                ips.append(primary_ip)
        except Exception:
            pass
        finally:
            s.close()

        # 2. Hostname resolution
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass

    return ips

def detect_hotspot_ip() -> str:
    """
    Finds the best IP to serve the captive portal to connected customer phones.
    Standard Windows Mobile Hotspot assigns 192.168.137.1.
    If not found, falls back to the first available local IP or 127.0.0.1.
    """
    ips = get_local_ip_addresses()

    # Priority 1: Standard Windows Mobile Hotspot IP (192.168.137.x)
    for ip in ips:
        if ip.startswith("192.168.137."):
            return ip

    # Priority 2: Any private subnet IP (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
    for ip in ips:
        if ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
            return ip

    # Fallback
    return ips[0] if ips else "127.0.0.1"

def check_mobile_hotspot_status() -> Dict[str, Any]:
    """
    Checks if Windows Mobile Hotspot is likely active by inspecting local IP interfaces.
    Zero Administrator privileges required.
    """
    ips = get_local_ip_addresses()
    has_hotspot_ip = any(ip.startswith("192.168.137.") for ip in ips)
    best_ip = detect_hotspot_ip()

    return {
        "hotspot_active": has_hotspot_ip,
        "server_ip": best_ip,
        "available_ips": ips,
        "status_message": "نقطة اتصال الهواتف (Mobile Hotspot) مفعلة وجاهزة بنجاح ✅" if has_hotspot_ip else "يرجى تفعيل (Mobile Hotspot) من إعدادات ويندوز لبث الواي فاي للزبائن ⚠️"
    }
