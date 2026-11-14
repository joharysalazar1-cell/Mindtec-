param(
 [Parameter(Mandatory=$true)][string]$PythonPath,
 [Parameter(Mandatory=$true)][string]$ConfigPath,
 [Parameter(Mandatory=$true)][string]$RuntimePath
)
$ErrorActionPreference = 'Stop'
$supervisorScript = Join-Path $PSScriptRoot 'supervisor.py'
$pythonExecutable = (Resolve-Path -LiteralPath $PythonPath).Path
$configurationFile = (Resolve-Path -LiteralPath $ConfigPath).Path
$runtimeDirectory = [System.IO.Path]::GetFullPath($RuntimePath)
if (-not (Test-Path -LiteralPath $supervisorScript -PathType Leaf)) { throw 'Missing supervisor script' }
if ([System.IO.Path]::GetFileName($pythonExecutable) -ne 'pythonw.exe') { throw 'Use pythonw.exe for a hidden startup process' }
foreach ($argument in @($supervisorScript,$configurationFile,$runtimeDirectory)) {
 if ($argument.Contains('"') -or $argument.EndsWith('\')) { throw 'Unsupported command argument' }
}
$startupFolder = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startupFolder 'MindTEC Auditoria local.lnk'
$shellObject = New-Object -ComObject WScript.Shell
$shortcut = $shellObject.CreateShortcut($shortcutPath)
if ((Test-Path -LiteralPath $shortcutPath) -and $shortcut.TargetPath -and $shortcut.TargetPath -ne $pythonExecutable) { throw 'A different startup target already uses this name' }
$shortcut.TargetPath = $pythonExecutable
$shortcut.Arguments = '"' + $supervisorScript + '" --config "' + $configurationFile + '" --runtime "' + $runtimeDirectory + '"'
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.WindowStyle = 7
$shortcut.Description = 'Supervisa los observadores locales de auditoría al iniciar sesión. No descarga Scan automáticamente.'
$shortcut.Save()
[pscustomobject]@{ Shortcut=$shortcutPath; Target=$shortcut.TargetPath; Arguments=$shortcut.Arguments; Scope='Current user logon'; Hidden=$true }
