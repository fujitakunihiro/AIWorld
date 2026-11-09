param([string]$EngineRoot='D:\Epic Games\UE_5.8')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
if(@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'}).Count){throw 'Close AIWorld before lane bake'}
& (Join-Path $repo 'gis\.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'generate_paris_lane.py')
if($LASTEXITCODE -ne 0){throw 'Lane generation failed'}
$script=Join-Path $PSScriptRoot 'bake-paris-lane.py';$log=Join-Path (Split-Path $project) 'Saved\paris-lane-bake.log'
& (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe') $project -run=pythonscript "-script=$script" -CustomConfig=ParisPhotoreal -unattended -nullrhi -nosound -nosplash -stdout "-abslog=$log"
if($LASTEXITCODE -ne 0 -or -not(Select-String -LiteralPath $log -Pattern 'PARIS_LANE_ASSETS_READY' -Quiet)){throw 'Lane bake failed'}
