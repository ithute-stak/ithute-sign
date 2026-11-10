@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Run build-windows.bat first & pause & exit /b 1)
.venv\Scripts\python.exe app\main.py
