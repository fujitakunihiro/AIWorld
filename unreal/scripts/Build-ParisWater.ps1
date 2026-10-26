param([string]$EngineRoot='D:\Epic Games\UE_5.8')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$running=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'})
if($running.Count){throw 'Close the AIWorld Unreal preview/editor before replacing water materials'}
& (Join-Path $repo 'gis\.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'generate_paris_water.py')
if($LASTEXITCODE -ne 0){throw 'Water shoreline generation failed'}
$editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$script=Join-Path $PSScriptRoot 'bake-paris-water.py'
$log=Join-Path (Split-Path $project) 'Saved\paris-water-bake.log'
& $editor $project '-run=pythonscript' "-script=$script" '-unattended' '-nullrhi' '-nosplash' '-stdout' '-UTF8Output' "-abslog=$log"
if($LASTEXITCODE -ne 0 -or -not(Select-String -LiteralPath $log -Pattern 'PARIS_WATER_ASSETS_READY' -Quiet)){throw 'Water material generation failed; inspect Saved/paris-water-bake.log'}
