param([string]$EngineRoot='D:\Epic Games\UE_5.8')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$running=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'})
if($running.Count){throw 'Close the AIWorld preview/editor before rebuilding street decoration'}
& (Join-Path $repo 'gis\.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'generate_paris_luxury.py')
if($LASTEXITCODE -ne 0){throw 'Luxury decoration generation failed'}
$log=Join-Path (Split-Path $project) 'Saved\paris-luxury-bake.log'
# Export assets without building unrelated editor shaders. Capture-ParisLuxury
# validates the actual DX12/SM6 game rendering and rejects shader fallbacks.
& (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe') $project '-run=pythonscript' ('-script='+(Join-Path $PSScriptRoot 'bake-paris-luxury.py')) -CustomConfig=ParisPhotoreal -unattended -nullrhi -nosound -nosplash -stdout -UTF8Output ('-abslog='+$log)
if($LASTEXITCODE -ne 0 -or -not(Select-String -LiteralPath $log -Pattern 'PARIS_LUXURY_ASSETS_READY' -Quiet) -or (Select-String -LiteralPath $log -Pattern 'Failed to compile Material|LogMaterial: Error|LogPython: Error' -Quiet)){throw 'Luxury decoration bake failed; inspect Saved/paris-luxury-bake.log'}
