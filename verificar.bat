@echo off
rem Diagnostico de la instalacion y del hardware (camara, proyector).  verificar.bat --sin-hardware
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
".env\Scripts\python.exe" verificar.py %*
echo.
pause
