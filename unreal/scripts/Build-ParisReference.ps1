param([string]$EngineRoot='D:\Epic Games\UE_5.8')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$python=Join-Path $repo 'gis\.venv\Scripts\python.exe'
if(@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'}).Count){throw 'Close AIWorld before building reference assets'}
& $python (Join-Path $PSScriptRoot 'fetch_paris_nature.py') --reference
if($LASTEXITCODE -ne 0){throw 'Reference tree acquisition failed; pinned local files can be used offline'}
& $python (Join-Path $PSScriptRoot 'generate_paris_reference.py')
if($LASTEXITCODE -ne 0){throw 'Reference geometry generation failed'}
$script=Join-Path $PSScriptRoot 'bake-paris-reference.py'
$log=Join-Path (Split-Path $project) 'Saved\paris-reference-bake.log'
& (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe') $project -run=pythonscript "-script=$script" -CustomConfig=ParisPhotoreal -unattended -nullrhi -nosound -nosplash -stdout -UTF8Output "-abslog=$log"
if($LASTEXITCODE -ne 0 -or -not(Select-String -LiteralPath $log -Pattern 'PARIS_REFERENCE_ASSETS_READY' -Quiet)){throw 'Reference asset bake failed'}
