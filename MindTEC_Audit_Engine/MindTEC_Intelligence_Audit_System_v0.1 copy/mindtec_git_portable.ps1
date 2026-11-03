# MindTEC Intelligence System - preparacion y publicacion segura
# PowerShell 5.1+ | Ejecutar desde la raiz del proyecto
param(
    [ValidateSet('Preparar','Publicar')][string]$Modo = 'Preparar',
    [string]$RepoUrl = '',
    [string]$Branch = 'main'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Info($msg) { Write-Host "[MindTEC] $msg" -ForegroundColor Cyan }
function Fail($msg) { throw $msg }
function Assert-Command($cmd) { if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { Fail "No se encontro '$cmd'. Instalalo antes de continuar." } }
function Is-Tracked($path) { & git ls-files --error-unmatch -- "$path" 2>$null | Out-Null; return ($LASTEXITCODE -eq 0) }

$root = (Get-Location).Path
if (-not (Test-Path (Join-Path $root 'app.py')) -or -not (Test-Path (Join-Path $root 'src'))) {
    Fail 'Abre PowerShell en la raiz del proyecto (donde estan app.py y src/) y vuelve a ejecutar.'
}
Assert-Command git
Assert-Command python
Info "Proyecto: $root"

# Archivo gitignore de seguridad: se anade sin eliminar reglas previas.
$ignorePath = Join-Path $root '.gitignore'
$ignore = @'

# --- MindTEC: exclusion de datos, credenciales y artefactos locales ---
.venv/
venv/
env/
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.streamlit/secrets.toml
.env
.env.*
!.env.example
*.pem
*.key
*.p12
*.pfx
id_rsa*
id_ed25519*
credentials.json
service-account*.json
*.sqlite
*.sqlite3
*.db
*.log
*.zip
*.7z
*.bak
*.backup
*_backup_*.py
requirements_backup.txt
.vscode/
.idea/
.DS_Store
Thumbs.db
# No publicar datos de clientes, ni aunque esten procesados.
data/raw/**
data/staging/**
data/processed/**
data/outputs/**
data/reference/**
!data/raw/.gitkeep
!data/staging/.gitkeep
!data/processed/.gitkeep
!data/outputs/.gitkeep
!data/reference/.gitkeep
# No subir archivos de exportacion o fuentes tabulares fuera de data
*.csv
*.xlsx
*.xls
*.parquet
*.feather
*.sav
*.dta
*.jsonl
# La carpeta config/rules puede contener reglas publicables; revisar manualmente.
'@
$currentIgnore = if (Test-Path $ignorePath) { Get-Content $ignorePath -Raw } else { '' }
if ($currentIgnore -notmatch 'MindTEC: exclusion de datos') {
    Add-Content -Path $ignorePath -Value $ignore -Encoding UTF8
    Info 'Reglas de exclusion agregadas a .gitignore.'
}

# Crear directorios de datos en nuevas maquinas sin copiar datos sensibles.
foreach ($folder in @('data/raw','data/staging','data/processed','data/outputs','data/reference')) {
    $p = Join-Path $root $folder
    New-Item -ItemType Directory -Path $p -Force | Out-Null
    $keep = Join-Path $p '.gitkeep'
    if (-not (Test-Path $keep)) { New-Item -ItemType File -Path $keep | Out-Null }
}

# Dependencias: congelar versiones del entorno activo como referencia (no garantiza portabilidad Linux).
$pythonPath = (& python -c 'import sys; print(sys.executable)').Trim()
Info "Python: $pythonPath"
& python -m pip freeze --disable-pip-version-check | Set-Content -Path (Join-Path $root 'requirements-lock-local.txt') -Encoding UTF8
# requirements.txt existente podria tener '\n' literales. No sobrescribirlo automaticamente.
$reqPath = Join-Path $root 'requirements.txt'
if (Test-Path $reqPath) {
    $req = Get-Content $reqPath -Raw
    if ($req.Contains('\n')) { Write-Warning 'requirements.txt parece contener \n literales: corrigelo antes de clonar. No se modifico.' }
}
# Lock local puede contener rutas, referencias privadas o paquetes de Windows: no versionarlo.
if ((Get-Content $ignorePath -Raw) -notmatch '(?m)^requirements-lock-local\.txt$') {
    Add-Content $ignorePath "`nrequirements-lock-local.txt" -Encoding UTF8
}

# Guia reproducible de instalacion en otra maquina.
$setup = @'
param([switch]$Instalar)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path 'app.py')) { throw 'Ejecuta este script desde la raiz del proyecto.' }
python -m venv .venv
$py = if ($IsWindows -or $env:OS -eq 'Windows_NT') { '.venv/Scripts/python.exe' } else { '.venv/bin/python' }
& $py -m pip install --upgrade pip
if (Test-Path 'requirements.txt') { & $py -m pip install -r requirements.txt }
Write-Host 'Entorno creado. Ejecuta la app con:'
Write-Host "  $py -m streamlit run app.py"
'@
Set-Content -Path (Join-Path $root 'setup_entorno.ps1') -Value $setup -Encoding UTF8

# Verificacion conservadora de archivos que podrian contener secretos.
$patterns = @('(?i)sk-[A-Za-z0-9_-]{15,}', '(?i)gh[pousr]_[A-Za-z0-9]{20,}', '(?i)-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----', '(?i)(api[_-]?key|password|secret|token)\s*[:=]\s*["''][^"'']{8,}["'']')
$codeFiles = Get-ChildItem -Path $root -Recurse -File -Include *.py,*.toml,*.yaml,*.yml,*.ini,*.cfg,*.md,*.txt -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch '[\\/](\.venv|venv|\.git|data|__pycache__)[\\/]' }
$hits = @()
foreach ($f in $codeFiles) {
    foreach ($pat in $patterns) {
        if (Select-String -Path $f.FullName -Pattern $pat -Quiet -ErrorAction SilentlyContinue) { $hits += $f.FullName; break }
    }
}
if ($hits.Count -gt 0) {
    Write-Warning 'Posibles secretos o credenciales en estos archivos. Revisalos antes de publicar:'
    $hits | Sort-Object -Unique | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
    if ($Modo -eq 'Publicar') { Fail 'Publicacion detenida por posibles secretos. Revisa los archivos y vuelve a ejecutar.' }
}

if (-not (Test-Path (Join-Path $root '.git'))) {
    & git init
    if ($LASTEXITCODE -ne 0) { Fail 'git init fallo.' }
    Info 'Repositorio Git local creado.'
}

# IMPORTANTE: gitignore no borra datos que ya hayan sido versionados.
$trackedSensitive = & git ls-files -- 'data/**' '*.csv' '*.xlsx' '*.parquet' '.env' '.streamlit/secrets.toml'
$trackedSensitive = @($trackedSensitive | Where-Object { $_ -and $_ -notmatch '\.gitkeep$' })
if ($trackedSensitive.Count -gt 0) {
    Write-Warning 'Estos archivos sensibles YA ESTAN VERSIONADOS. .gitignore NO los protege:'
    $trackedSensitive | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
    Fail 'Detenido: elimina esos archivos del indice con git rm --cached y revisa el historial antes de publicar.'
}

# Agregar SOLO rutas de codigo, documentacion y pruebas. No usar git add .
$allowed = @('mindtec_git_portable.ps1','.gitignore','README.md','requirements.txt','setup_entorno.ps1','app.py','config.py','main.py','src','interface','docs','tests','config/rules','data/raw/.gitkeep','data/staging/.gitkeep','data/processed/.gitkeep','data/outputs/.gitkeep','data/reference/.gitkeep')
foreach ($item in $allowed) {
    if (Test-Path (Join-Path $root $item)) { & git add -- $item; if ($LASTEXITCODE -ne 0) { Fail "No se pudo agregar $item" } }
}
Info 'Archivos preparados para Git:'
& git diff --cached --stat
Info 'Revisa el contenido con: git diff --cached'

if ($Modo -eq 'Preparar') {
    Write-Host "`nPreparacion finalizada. Revisa los archivos y ejecuta despues:" -ForegroundColor Green
    Write-Host '  .\mindtec_git_portable.ps1 -Modo Publicar -RepoUrl "https://github.com/USUARIO/REPO.git"'
    exit 0
}
if ([string]::IsNullOrWhiteSpace($RepoUrl)) { Fail 'Para publicar, proporciona -RepoUrl con la URL del repositorio PRIVADO creado en GitHub.' }
if ($RepoUrl -notmatch '^https://github\.com/[^/]+/[^/]+\.git$' -and $RepoUrl -notmatch '^git@github\.com:[^/]+/[^/]+\.git$') {
    Fail 'RepoUrl debe ser https://github.com/USUARIO/REPO.git o git@github.com:USUARIO/REPO.git'
}
$answer = Read-Host 'CONFIRMA: repositorio PRIVADO, autorizacion de MindTEC y archivos revisados. Escribe PUBLICAR'
if ($answer -cne 'PUBLICAR') { Fail 'Publicacion cancelada.' }
& git diff --cached --quiet
$changes = $LASTEXITCODE -ne 0
if ($changes) {
    & git commit -m 'Preparar MindTEC Intelligence System para portabilidad'
    if ($LASTEXITCODE -ne 0) { Fail 'git commit fallo. Configura git user.name y git user.email.' }
} else { Info 'No hay cambios nuevos para commit.' }
& git branch -M $Branch
$existing = (& git remote get-url origin 2>$null)
if ($LASTEXITCODE -eq 0 -and $existing) {
    if ($existing.Trim() -ne $RepoUrl) { Fail "El remoto origin ya apunta a $existing. No se modifico." }
} else {
    & git remote add origin $RepoUrl
    if ($LASTEXITCODE -ne 0) { Fail 'No se pudo configurar origin.' }
}
& git push -u origin $Branch
if ($LASTEXITCODE -ne 0) { Fail 'Push fallido. Comprueba autenticacion y permisos del repositorio.' }
Info 'Publicacion terminada. Los datos y secretos locales NO se han incluido.'
