param([string]$EngineRoot='D:\Epic Games\UE_5.8')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$running=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'})
if($running.Count){throw 'Close the AIWorld preview/editor before replacing tree assets'}
& (Join-Path $repo 'gis\.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'fetch_paris_nature.py')
if($LASTEXITCODE -ne 0){throw 'Verified CC0 tree acquisition failed'}
$editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$script=Join-Path $PSScriptRoot 'create-paris-nature.py'
$log=Join-Path (Split-Path $project) 'Saved\paris-nature-bake.log'
& $editor $project '-run=pythonscript' "-script=$script" '-unattended' '-nullrhi' '-nosplash' '-stdout' '-UTF8Output' "-abslog=$log"
if($LASTEXITCODE -ne 0 -or -not(Select-String -LiteralPath $log -Pattern 'PARIS_PHOTO_NATURE_READY|PARIS_PHOTO_NATURE_CACHED' -Quiet)){throw 'Tree material bake failed; inspect Saved/paris-nature-bake.log'}
