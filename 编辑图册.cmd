@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在打开小满 flower 图册编辑器……
py -3 catalog_manager.py
if errorlevel 1 (
  echo.
  echo 启动失败，请确认电脑已经安装 Python。
  pause
)

