@echo off
rem Abre la interfaz web (doble clic o el acceso directo del escritorio).
rem Al cambiar de montaje el servidor termina con el codigo 3 y este archivo lo vuelve a abrir.
rem Argumentos opcionales: --puerto 8080  --sin-navegador  --host 0.0.0.0
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set TESIS_LANZADOR=bat
if not exist ".env\Scripts\python.exe" (
  echo No esta instalado todavia: ejecuta primero instalar.bat
  pause
  exit /b 1
)
:inicio
".env\Scripts\python.exe" interfaz\servidor.py %*
if %ERRORLEVEL% EQU 3 (
  set TESIS_REINICIO=1
  goto inicio
)
pause
