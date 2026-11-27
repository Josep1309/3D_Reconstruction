# Instala el sistema de reconstrucción 3D por franjas en este computador (Windows 10/11).
# Se ejecuta con instalar.bat (doble clic) o desde PowerShell:
#
#   .\instalar.bat                                    entorno de Python + dependencias + patrones + verificación
#   .\instalar.bat -PySpin C:\ruta\spinnaker_python-...-cp310-cp310-win_amd64.whl   además PySpin (cámara FLIR)
#   .\instalar.bat -Python C:\ruta\python.exe         usa ese intérprete para crear el entorno
#   .\instalar.bat -SinVerificar                      no corre verificar.py al final
#
# Se puede ejecutar varias veces: lo que ya está hecho se omite. Detalles: MANUAL.md §20.9.
param(
    [string]$Python = "",
    [string]$PySpin = "",
    [switch]$SinVerificar,
    [switch]$SinAccesoDirecto
)

# "Continue": en Windows PowerShell 5.1, con "Stop" cualquier texto que un programa escriba en
# stderr (avisos de pip, un import que falla con 2>$null) detiene el script. Se revisa $LASTEXITCODE.
$ErrorActionPreference = "Continue"
$Raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Raiz
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

function Ok($t)    { Write-Host "  [OK] $t" -ForegroundColor Green }
function Aviso($t) { Write-Host "  [AVISO] $t" -ForegroundColor Yellow }
function Fallo($t) { Write-Host "  [ERROR] $t" -ForegroundColor Red; exit 1 }

Write-Host "== Instalación en $Raiz"

# ---------------------------------------------------------------- 1. Python 3.10
function Version-De($exe, $extra) {
    try {
        # sin comillas dobles dentro del argumento: PowerShell 5.1 las pasa mal a los programas
        $v = & $exe @extra -c "import sys, struct; print('%d.%d %d' % (sys.version_info[0], sys.version_info[1], struct.calcsize('P') * 8))" 2>$null
        if ($LASTEXITCODE -eq 0 -and $v) { return "$v".Trim() }
    } catch { }
    return $null
}

$PyExe = $null; $PyArgs = @()
if ($Python) {
    $PyExe = $Python
} else {
    $candidatos = @(
        @("py", @("-3.10")),
        @("$env:LOCALAPPDATA\Programs\Python\Python310\python.exe", @()),
        @("$env:ProgramFiles\Python310\python.exe", @()),
        @("python", @())
    )
    foreach ($c in $candidatos) {
        $v = Version-De $c[0] $c[1]
        if ($v -and $v.StartsWith("3.10 ")) { $PyExe = $c[0]; $PyArgs = $c[1]; break }
    }
}
if (-not $PyExe) {
    Aviso "No se encontró Python 3.10 (el wheel de PySpin es para 3.10)."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        $r = Read-Host "  ¿Instalarlo ahora con winget? (S/n)"
        if ($r -eq "" -or $r -match "^[sSyY]") {
            winget install --id Python.Python.3.10 -e --scope user --accept-package-agreements --accept-source-agreements
            $exe = "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe"
            if (Test-Path $exe) { $PyExe = $exe; $PyArgs = @() }
        }
    }
    if (-not $PyExe) {
        Fallo "Instala Python 3.10 de 64 bits (python.org o 'winget install Python.Python.3.10') y vuelve a ejecutar instalar.bat."
    }
}
$v = Version-De $PyExe $PyArgs
if (-not $v) { Fallo "No se pudo ejecutar $PyExe" }
if (-not $v.EndsWith(" 64")) { Fallo "Python $v es de 32 bits: hace falta el de 64 bits." }
if ($v.StartsWith("3.10 ")) { Ok "Python $v bits ($PyExe $PyArgs)" }
else { Aviso "Python $($v.Split(' ')[0]): funciona, pero el wheel de PySpin debe ser de esa misma versión (MANUAL.md §20.3)." }

# ---------------------------------------------------------------- 2. Entorno virtual (.env)
$Py = Join-Path $Raiz ".env\Scripts\python.exe"
if (Test-Path $Py) {
    Ok "Entorno virtual .env ya existe ($(& $Py -V))"
} else {
    & $PyExe @PyArgs -m venv .env
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Py)) { Fallo "No se pudo crear el entorno virtual .env" }
    Ok "Entorno virtual creado en .env\"
}

# ---------------------------------------------------------------- 3. Dependencias
Write-Host "== Instalando dependencias (requirements.txt)…"
& $Py -m pip install --quiet --upgrade pip
& $Py -m pip install --quiet -r requirements.txt
if ($LASTEXITCODE -ne 0) { Fallo "pip no pudo instalar requirements.txt (¿hay internet?)" }
Ok "numpy, opencv-python, matplotlib y hidapi instalados"

# ---------------------------------------------------------------- 4. PySpin (opcional)
$sdk = @("$env:ProgramFiles\Teledyne\Spinnaker", "$env:ProgramFiles\FLIR Systems\Spinnaker") | Where-Object { Test-Path $_ }
if ($PySpin) {
    if (-not (Test-Path $PySpin)) { Fallo "No existe el archivo '$PySpin'" }
    if (-not $sdk) { Aviso "No se encontró el Spinnaker SDK en Archivos de programa: instálalo primero (MANUAL.md §20.3)." }
    & $Py -m pip install --quiet "$PySpin"
    & $Py -c "import PySpin" 2>$null
    if ($LASTEXITCODE -eq 0) { Ok "PySpin instalado" }
    else { Fallo "PySpin se instaló pero no carga: revisa que el SDK y el wheel sean de la misma versión (MANUAL.md §20.3)." }
} else {
    & $Py -c "import PySpin" 2>$null
    if ($LASTEXITCODE -eq 0) { Ok "PySpin ya está instalado" }
    else { Aviso "PySpin no instalado: no se podrá capturar (procesar y visualizar sí). Usa: instalar.bat -PySpin <archivo.whl>" }
}

# ---------------------------------------------------------------- 5. Patrones de los dos montajes
foreach ($m in @("lightcrafter", "hdmi_dell")) {
    $env:TESIS_MONTAJE = $m
    $dir = & $Py -c "from datos_sistema import configuracion as c; print(c.DIR_PATRONES)"
    $n = @(Get-ChildItem -Path $dir -Filter "f_*.bmp" -ErrorAction SilentlyContinue).Count
    $necesarios = [int](& $Py -c "from datos_sistema import configuracion as c; print(c.IMAGENES_POR_CICLO)")
    if ($n -lt $necesarios) {
        & $Py -m captura.secuencia_patrones | Out-Null
        if ($LASTEXITCODE -ne 0) { Fallo "No se pudieron generar los patrones de '$m'" }
        Ok "Patrones de '$m' generados en $dir"
    } else {
        Ok "Patrones de '$m' presentes"
    }
}
Remove-Item Env:\TESIS_MONTAJE

# ---------------------------------------------------------------- 6. Acceso directo en el escritorio
if (-not $SinAccesoDirecto) {
    try {
        $escritorio = [Environment]::GetFolderPath("Desktop")
        $sh = New-Object -ComObject WScript.Shell
        $ad = $sh.CreateShortcut((Join-Path $escritorio "Reconstrucción 3D.lnk"))
        $ad.TargetPath = Join-Path $Raiz "iniciar_interfaz.bat"
        $ad.WorkingDirectory = $Raiz
        $ad.Save()
        Ok "Acceso directo «Reconstrucción 3D» en el escritorio"
    } catch { Aviso "No se pudo crear el acceso directo: abre iniciar_interfaz.bat directamente." }
}

# ---------------------------------------------------------------- 7. Verificación
if (-not $SinVerificar) {
    Write-Host ""
    & $Py verificar.py
}
Write-Host ""
Write-Host "Listo. Interfaz web:  iniciar_interfaz.bat  (o el acceso directo del escritorio)"
Write-Host "       Por script:    .env\Scripts\python.exe pipeline.py"
