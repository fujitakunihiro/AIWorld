param([string]$EngineRoot='D:\Epic Games\UE_5.8')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$running=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'})
if($running.Count){throw 'Close the AIWorld preview/editor before rebuilding ground assets'}
$backup=Join-Path $repo ('backups\paris-ground-assets-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Force -Path $backup,(Join-Path $backup 'Materials'),(Join-Path $backup 'Ground'),(Join-Path $backup 'Data'),(Join-Path $backup 'Weather') | Out-Null
Copy-Item (Join-Path $repo 'unreal\AIWorld\Content\Materials\*.uasset') (Join-Path $backup 'Materials')
Copy-Item (Join-Path $repo 'unreal\AIWorld\Content\ParisPhotoreal\Ground\*.uasset') (Join-Path $backup 'Ground')
Copy-Item (Join-Path $repo 'unreal\AIWorld\Content\Weather\*.uasset') (Join-Path $backup 'Weather')
Copy-Item (Join-Path $repo 'unreal\AIWorld\Content\Data\paris-photo-ground*.json') (Join-Path $backup 'Data')
$python=Join-Path $repo 'gis\.venv\Scripts\python.exe'
& $python (Join-Path $PSScriptRoot 'generate_paris_ground_display.py')
if($LASTEXITCODE -ne 0){throw 'Ground geometry generation failed'}
& $python (Join-Path $PSScriptRoot 'generate_paris_rain_audio.py')
if($LASTEXITCODE -ne 0){throw 'Rain audio generation failed'}
$log=Join-Path (Split-Path $project) 'Saved\paris-ground-continuity-bake.log'
& (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe') $project '-run=pythonscript' ('-script='+(Join-Path $PSScriptRoot 'bake-paris-ground-continuity.py')) -CustomConfig=ParisPhotoreal -unattended -nullrhi -nosound -nosplash -stdout -UTF8Output ('-abslog='+$log)
if($LASTEXITCODE -ne 0 -or -not(Select-String -LiteralPath $log -Pattern 'PARIS_GROUND_CONTINUITY_READY' -Quiet) -or (Select-String -LiteralPath $log -Pattern 'Failed to compile Material|LogMaterial: Error|LogPython: Error' -Quiet)){throw 'Ground asset bake failed; inspect Saved/paris-ground-continuity-bake.log'}
