"""
QR Code generator for customer Wi-Fi login vouchers.
"""
import os
from pathlib import Path

def generate_voucher_qr(code: str, portal_url: str, save_path: str = None) -> str:
    """
    Generates a QR code image that takes the customer directly to the login portal
    with their voucher code automatically populated.
    """
    full_url = f"{portal_url}?code={code}"
    
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(full_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        if not save_path:
            from src.utils.config import DATA_DIR
            qr_dir = DATA_DIR / "qrcodes"
            os.makedirs(qr_dir, exist_ok=True)
            save_path = str(qr_dir / f"voucher_{code}.png")

        img.save(save_path)
        return save_path
    except ImportError:
        return ""
    except Exception as e:
        print(f"[QR Helper] Error generating QR code: {e}")
        return ""

def generate_static_wall_qr(portal_url: str = "http://192.168.137.1:8080/", save_path: str = None) -> str:
    """
    Generates the SINGLE PERMANENT WALL QR CODE that is printed once and displayed in the shop.
    When any customer scans it, it opens the portal and issues them unique temporary credentials.
    """
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=12,
            border=3,
        )
        qr.add_data(portal_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#090d16", back_color="#ffffff")

        if not save_path:
            from src.utils.config import DATA_DIR
            qr_dir = DATA_DIR / "qrcodes"
            os.makedirs(qr_dir, exist_ok=True)
            save_path = str(qr_dir / "static_wall_qr.png")

        img.save(save_path)
        return save_path
    except ImportError:
        return ""
    except Exception as e:
        print(f"[QR Helper] Error generating wall QR: {e}")
        return ""

