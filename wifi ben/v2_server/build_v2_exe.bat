@echo off
setlocal
chcp 65001 >nul
echo ========================================================
echo  WiFi Shop Manager v2 - Executable Builder (.exe)
echo  [Zero Admin Rights / No UAC Required]
echo ========================================================
echo.

set "CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" (
    set "CSC=C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
)

echo [1/1] Compiling standalone executable WiFiShopManager_v2.exe...
if exist "%CSC%" (
    "%CSC%" /target:winexe /out:"..\WiFiShopManager_v2.exe" /r:System.dll,System.Core.dll,System.Drawing.dll,System.Windows.Forms.dll,System.Web.Extensions.dll /optimize+ "csharp\Program.cs"
    if %errorlevel% equ 0 (
        echo [OK] Successfully built: ..\WiFiShopManager_v2.exe
    ) else (
        echo [ERROR] Compilation failed.
    )
) else (
    echo [WARNING] Built-in C# compiler not found.
)

echo.
echo ========================================================
echo  Build complete! Double click WiFiShopManager_v2.exe to run.
echo ========================================================
pause

