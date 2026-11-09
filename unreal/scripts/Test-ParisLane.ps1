param([string]$EngineRoot='D:\Epic Games\UE_5.8',[switch]$NativeOnly)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if(-not $NativeOnly){
    & (Join-Path $repo 'gis\.venv\Scripts\python.exe') -m unittest discover -s (Join-Path $PSScriptRoot 'tests') -p test_paris_lane.py -v
    if($LASTEXITCODE -ne 0){throw 'Lane geometry/clearance validation failed'}
}
& (Join-Path $PSScriptRoot 'Test-ParisReference.ps1') -EngineRoot $EngineRoot -NativeOnly
if($LASTEXITCODE -ne 0){throw 'Reference regression validation failed'}
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1');$log=Join-Path (Split-Path $project) 'Saved\paris-lane-automation.log'
& (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe') $project -game -ParisTwin -ParisPhotoreal -ParisTwinLane -CustomConfig=ParisPhotoreal -nullrhi -unattended -nosplash '-ExecCmds=Automation RunTests ParisDigitalTwin.Live.LaneSurfacePropsAndRestoration' '-TestExit=Automation Test Queue Empty' "-abslog=$log" -stdout
if($LASTEXITCODE -ne 0 -or -not(Select-String -LiteralPath $log -Pattern 'Result=\{Success\}.*Name=\{LaneSurfacePropsAndRestoration\}' -Quiet) -or (Select-String -LiteralPath $log -Pattern 'Result=\{Fail\}|Fatal error' -Quiet)){throw 'Lane runtime validation failed'}
