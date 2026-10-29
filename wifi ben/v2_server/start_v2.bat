@echo off
chcp 65001 > nul
title WiFi Shop Manager v2 - Local Web Server
echo =================================================================
echo        📶 WiFi Shop Manager v2 - Local Web Server
echo  (إصدار خفيف بدون صلاحيات مسؤول - Zero Admin / UAC Required)
echo =================================================================
echo.

where python >nul 2>nul
if %errorlevel% equ 0 (
    python app.py
    goto end
)

where py >nul 2>nul
if %errorlevel% equ 0 (
    py app.py
    goto end
)

if exist "..\WiFiShopManager_v2.exe" (
    echo [INFO] تشغيل النسخة التنفيذية المباشرة WiFiShopManager_v2.exe...
    start "" "..\WiFiShopManager_v2.exe"
    goto end
)

echo [تنبيه] لم يتم العثور على بايثون مثبت في مسار النظام (PATH).
echo يمكنك تشغيل النسخة التنفيذية المباشرة WiFiShopManager_v2.exe بالنقر عليها مرتين.
echo.
pause

:end
