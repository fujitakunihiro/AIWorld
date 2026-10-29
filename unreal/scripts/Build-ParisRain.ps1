param([string]$EngineRoot='D:\Epic Games\UE_5.8')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$running=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'})
if($running.Count){throw 'Close the AIWorld preview/editor before baking rain materials'}
$backup=Join-Path $repo ('backups\paris-rain-assets-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backup -Force | Out-Null
Copy-Item -Path (Join-Path $repo 'unreal\AIWorld\Content\Materials\*.uasset') -Destination $backup
& (Join-Path $repo 'gis\.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'generate_paris_rain_audio.py')
if($LASTEXITCODE -ne 0){throw 'Original rain audio synthesis failed'}
$editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$log=Join-Path (Split-Path $project) 'Saved\paris-rain-bake.log'
& $editor $project '-run=pythonscript' ('-script='+(Join-Path $PSScriptRoot 'bake-paris-rain.py')) -unattended -nullrhi -nosound -nosplash -stdout -UTF8Output ('-abslog='+$log)
if($LASTEXITCODE -ne 0 -or -not(Select-String -LiteralPath $log -Pattern 'PARIS_RAIN_ASSETS_READY' -Quiet) -or (Select-String -LiteralPath $log -Pattern 'Failed to compile Material|LogMaterial: Error' -Quiet)){throw 'Rain asset bake failed; inspect Saved/paris-rain-bake.log'}
