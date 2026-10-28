param([string]$EngineRoot='D:\Epic Games\UE_5.8')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
New-Item -ItemType Directory -Path (Join-Path $repo 'unreal\AIWorld\Content\ParisPhotoreal\Cruise\Materials'),(Join-Path $repo 'unreal\AIWorld\Content\ParisPhotoreal\Cruise\Textures') -Force | Out-Null
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$running=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'})
if($running.Count){throw 'Close the AIWorld preview/editor before baking cruise assets'}
$python=Join-Path $repo 'gis\.venv\Scripts\python.exe'
& $python (Join-Path $PSScriptRoot 'fetch_paris_cruise.py')
if($LASTEXITCODE -ne 0){throw 'Cruise source verification failed'}
& $python (Join-Path $PSScriptRoot 'prepare_paris_cruise.py')
if($LASTEXITCODE -ne 0){throw 'Cruise preparation failed'}
$editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$log=Join-Path (Split-Path $project) 'Saved\paris-cruise-bake.log'
& $editor $project '-run=pythonscript' ('-script='+(Join-Path $PSScriptRoot 'bake-paris-cruise.py')) '-unattended' '-nullrhi' '-nosplash' '-stdout' '-UTF8Output' "-abslog=$log"
if($LASTEXITCODE -ne 0 -or -not(Select-String -LiteralPath $log -Pattern 'PARIS_CRUISE_ASSETS_READY' -Quiet)){throw 'Cruise bake failed; inspect Saved/paris-cruise-bake.log'}
