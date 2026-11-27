@echo off
rem Instala el sistema en Windows: Python, dependencias, PySpin, patrones y acceso directo.
rem Uso:  instalar.bat  [-PySpin C:\ruta\spinnaker_python-...-cp310-cp310-win_amd64.whl]  [-Python C:\ruta\python.exe]  [-SinVerificar]
rem Detalles en instalar.ps1 y en docs\MANUAL.md (seccion 20.9).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1" %*
echo.
pause
