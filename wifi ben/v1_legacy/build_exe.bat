@echo off
setlocal
echo ========================================================
echo  WiFi Shop Manager - Windows Executable Builder (.exe)
echo ========================================================
echo.

set "CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" (
    set "CSC=C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
)

echo [1/2] Compiling standalone Windows executable...
if exist "%CSC%" (
    "%CSC%" /target:winexe /out:"WiFiShopManager.exe" /win32icon:"src\assets\icon.ico" /win32manifest:"src\csharp\app.manifest" /r:System.dll,System.Core.dll,System.Drawing.dll,System.Windows.Forms.dll,System.Web.Extensions.dll /optimize+ "src\csharp\Program.cs"
    if %errorlevel% equ 0 (
        echo [OK] Successfully built: WiFiShopManager.exe
    ) else (
        echo [ERROR] Compilation failed.
    )
) else (
    echo [WARNING] Built-in C# compiler not found.
)

echo.
echo [2/2] Checking Python environment...
where pip >nul 2>nul
if %errorlevel% equ 0 (
    echo Python and Pip detected. Building optional PyInstaller bundle...
    pip install -r requirements.txt pyinstaller
    pyinstaller --noconfirm --onedir --windowed --name "WiFiShopManager-Py" --add-data "src/assets;assets" --icon "src/assets/icon.ico" src/main.py
) else (
    echo Standalone native executable WiFiShopManager.exe is ready for use without Python!
)

echo.
echo ========================================================
echo  Build complete! Double click WiFiShopManager.exe to run.
echo ========================================================
pause
