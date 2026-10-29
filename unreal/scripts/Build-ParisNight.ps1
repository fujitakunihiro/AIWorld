param([string]$EngineRoot='D:\Epic Games\UE_5.8')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$running=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'})
if($running.Count){throw 'Close the AIWorld preview/editor before baking night materials'}
$backup=Join-Path $repo ('backups\paris-night-assets-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backup -Force | Out-Null
foreach($file in @('M_ParisWindowGlass','M_ParisStainedGlass')){Copy-Item -LiteralPath (Join-Path $repo ('unreal\AIWorld\Content\Materials\'+$file+'.uasset')) -Destination $backup}
$log=Join-Path (Split-Path $project) 'Saved\paris-night-bake.log'
& (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe') $project -run=pythonscript ('-script='+(Join-Path $PSScriptRoot 'bake-paris-night.py')) -unattended -nullrhi -nosound -nosplash -stdout -UTF8Output ('-abslog='+$log)
if($LASTEXITCODE -ne 0 -or -not(Select-String -LiteralPath $log -Pattern 'PARIS_NIGHT_ASSETS_READY' -Quiet) -or (Select-String -LiteralPath $log -Pattern 'Failed to compile Material|LogMaterial: Error' -Quiet)){throw 'Night asset bake failed; inspect Saved/paris-night-bake.log'}
