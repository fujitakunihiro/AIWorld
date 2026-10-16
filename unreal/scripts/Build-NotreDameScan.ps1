param([string]$EngineRoot='D:\Epic Games\UE_5.8')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$running=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'})
if($running.Count){throw 'Close the AIWorld preview/editor before rebuilding the scanned facade'}
$python=Join-Path $repo 'gis\.venv\Scripts\python.exe'
& $python (Join-Path $PSScriptRoot 'fetch_notredame_facade.py')
if($LASTEXITCODE -ne 0){throw 'Verified historic facade acquisition failed'}
& $python (Join-Path $PSScriptRoot 'generate_notredame_scan.py')
if($LASTEXITCODE -ne 0){throw 'Observed surface generation failed'}
$editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
New-Item -ItemType Directory -Path (Join-Path (Split-Path $project) 'Content\ParisPhotoreal\NotreDameScan') -Force | Out-Null
$script=Join-Path $PSScriptRoot 'bake-notredame-scan.py'
& $editor $project '-run=pythonscript' "-script=$script" -CustomConfig=ParisPhotoreal -nullrhi -unattended -nosplash -stdout -UTF8Output
if($LASTEXITCODE -ne 0){throw 'Observed facade mesh/material generation failed'}
