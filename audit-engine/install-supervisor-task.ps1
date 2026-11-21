param(
 [Parameter(Mandatory=$true)][string]$PythonPath,
 [Parameter(Mandatory=$true)][string]$ConfigPath,
 [Parameter(Mandatory=$true)][string]$RuntimePath,
 [string]$TaskName='MindTEC-Auditoria-local'
)
$ErrorActionPreference='Stop'
$pythonExecutable=(Resolve-Path -LiteralPath $PythonPath).Path
$configurationFile=(Resolve-Path -LiteralPath $ConfigPath).Path
$runtimeDirectory=[System.IO.Path]::GetFullPath($RuntimePath)
$supervisorScript=Join-Path $PSScriptRoot 'supervisor.py'
if ([System.IO.Path]::GetFileName($pythonExecutable) -ne 'pythonw.exe') { throw 'Use pythonw.exe for hidden execution' }
foreach ($argument in @($supervisorScript,$configurationFile,$runtimeDirectory)) {
 if ($argument.Contains('"') -or $argument.EndsWith('\')) { throw 'Unsupported command argument' }
}
$arguments='"'+$supervisorScript+'" --config "'+$configurationFile+'" --runtime "'+$runtimeDirectory+'"'
$existing=Get-ScheduledTask -TaskName $TaskName -TaskPath '\' -ErrorAction SilentlyContinue
if ($existing) { throw 'A task already uses this name; inspect it before replacing anything' }
$identity=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action=New-ScheduledTaskAction -Execute $pythonExecutable -Argument $arguments -WorkingDirectory $PSScriptRoot
$trigger=New-ScheduledTaskTrigger -AtLogOn -User $identity
$recoveryTrigger=New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) -RepetitionInterval (New-TimeSpan -Minutes 1)
$principal=New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -Hidden
Register-ScheduledTask -TaskName $TaskName -TaskPath '\' -Action $action -Trigger @($trigger,$recoveryTrigger) -Principal $principal -Settings $settings -Description 'Supervisión local de Scan, facturas y linaje. Recuperación periódica de instancia única; respeta stop.request. No descarga Scan automáticamente.' | Select-Object TaskName,State
