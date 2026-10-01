@echo off
chcp 65001 >nul
title 手机相册备份服务
cd /d "%~dp0"
echo 正在启动备份服务, 备份目录: %~dp0received
echo 浏览器打开 http://localhost:8899 可查看状态
echo.
python backup_server.py 2>nul || py -3 backup_server.py
pause
