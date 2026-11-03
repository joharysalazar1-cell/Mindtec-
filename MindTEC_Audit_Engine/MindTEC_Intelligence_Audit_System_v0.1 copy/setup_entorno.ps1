param([switch]$Instalar)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path 'app.py')) { throw 'Ejecuta este script desde la raiz del proyecto.' }
python -m venv .venv
$py = if ($IsWindows -or $env:OS -eq 'Windows_NT') { '.venv/Scripts/python.exe' } else { '.venv/bin/python' }
& $py -m pip install --upgrade pip
if (Test-Path 'requirements.txt') { & $py -m pip install -r requirements.txt }
Write-Host 'Entorno creado. Ejecuta la app con:'
Write-Host "  $py -m streamlit run app.py"
