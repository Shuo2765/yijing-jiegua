@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ========================================
echo   易經解掛 - 請用新網址 :9080
echo   （不要再用舊的 :8080）
echo ========================================
echo.

REM 先結束殘留的 serve.py，避免連接埠被占用
echo 正在清理舊的伺服器行程...
powershell -NoProfile -Command ^
  "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'serve\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; Start-Sleep -Seconds 1"
echo.

if exist "%LocalAppData%\Programs\Python\Python313\python.exe" (
    "%LocalAppData%\Programs\Python\Python313\python.exe" serve.py
    goto :after
)
if exist "%LocalAppData%\Programs\Python\Python310\python.exe" (
    "%LocalAppData%\Programs\Python\Python310\python.exe" serve.py
    goto :after
)
py -3 serve.py
if errorlevel 1 python serve.py

:after
if errorlevel 1 (
    echo.
    echo 啟動失敗。若仍提示連接埠占用：
    echo   1. 關掉所有 start-server 黑色視窗
    echo   2. 再開一次本檔
    pause
    exit /b 1
)
pause
