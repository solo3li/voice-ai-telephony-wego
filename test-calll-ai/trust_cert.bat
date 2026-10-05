@echo off
echo =======================================================
echo Adding local certificate to Windows Trusted Root Store
echo =======================================================
certutil -user -addstore Root "%~dp0traefik\certs\local.crt"
echo.
echo Certificate trusted successfully!
echo Please restart your browser and visit https://app.localhost
pause
