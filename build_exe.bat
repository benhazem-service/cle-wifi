@echo off
echo ========================================================
echo  WiFi Shop Manager - Local Windows Build Script (.exe)
echo ========================================================
echo.

echo [1/3] Checking dependencies...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo [2/3] Building standalone executable...
pyinstaller --noconfirm --onedir --windowed ^
    --name "WiFiShopManager" ^
    --add-data "src/assets;assets" ^
    --icon "src/assets/icon.ico" ^
    src/main.py

echo.
echo [3/3] Build finished!
echo Executable located in: dist\WiFiShopManager\WiFiShopManager.exe
echo ========================================================
pause
