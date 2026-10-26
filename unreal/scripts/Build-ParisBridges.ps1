param([string]$EngineRoot='D:\Epic Games\UE_5.8')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$running=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'})
if($running.Count){throw 'Close the AIWorld preview/editor before replacing bridge assets'}
$python=Join-Path $repo 'gis\.venv\Scripts\python.exe'
foreach($script in @('fetch_paris_bridge_surfaces.py','generate_paris_bridges.py')){
    & $python (Join-Path $PSScriptRoot $script)
    if($LASTEXITCODE -ne 0){throw "Bridge preparation failed: $script"}
}
$editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$script=Join-Path $PSScriptRoot 'bake-paris-bridges.py'
$log=Join-Path (Split-Path $project) 'Saved\paris-bridges-bake.log'
& $editor $project '-run=pythonscript' "-script=$script" '-unattended' '-nullrhi' '-nosplash' '-stdout' '-UTF8Output' "-abslog=$log"
if($LASTEXITCODE -ne 0 -or -not(Select-String -LiteralPath $log -Pattern 'PARIS_BRIDGE_ASSETS_READY' -Quiet)){throw 'Bridge asset bake failed; inspect Saved/paris-bridges-bake.log'}
