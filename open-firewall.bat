@echo off
chcp 65001 >nul
echo 允許防火牆連入 TCP 9080、9443
echo （需系統管理員）
echo.
netsh advfirewall firewall delete rule name="Iching HTTP 9080" >nul 2>&1
netsh advfirewall firewall delete rule name="Iching HTTPS 9443" >nul 2>&1
netsh advfirewall firewall add rule name="Iching HTTP 9080" dir=in action=allow protocol=TCP localport=9080 profile=any
netsh advfirewall firewall add rule name="Iching HTTPS 9443" dir=in action=allow protocol=TCP localport=9443 profile=any
if errorlevel 1 (
    echo 失敗：請右鍵此檔 →「以系統管理員身分執行」
) else (
    echo 完成
)
echo.
pause
