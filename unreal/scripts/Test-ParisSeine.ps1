param([string]$EngineRoot='D:\Epic Games\UE_5.8')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
& (Join-Path $repo 'gis\.venv\Scripts\python.exe') -m unittest discover -s (Join-Path $PSScriptRoot 'tests') -p test_paris_seine.py -v
if($LASTEXITCODE -ne 0){throw 'Seine geographic validation failed'}
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
if(@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'}).Count){throw 'Close AIWorld before automation'}
$groups=@(
    @{Name='seine';Tests=@('ReferenceArchitectureAndRestoration');Flags=@('-ParisTwinSeine')},
    @{Name='environment';Tests=@('NightLightingAndDayRestoration','RainLifecycleAndShelter');Flags=@()},
    @{Name='reference';Tests=@('ReferenceArchitectureAndRestoration');Flags=@('-ParisTwinReferenceLook')},
    @{Name='lane';Tests=@('LaneSurfacePropsAndRestoration');Flags=@('-ParisTwinLane')}
)
foreach($group in $groups){
    $log=Join-Path (Split-Path $project) ('Saved\paris-seine-'+$group.Name+'-automation.log')
    $filter=(($group.Tests | ForEach-Object {'ParisDigitalTwin.Live.'+$_}) -join '+')
    $args=@($project,'-game','-ParisTwin','-ParisPhotoreal','-CustomConfig=ParisPhotoreal','-nullrhi','-unattended','-nosplash',('-ExecCmds=Automation RunTests '+$filter),'-TestExit=Automation Test Queue Empty',('-abslog='+$log),'-stdout','-UTF8Output')+$group.Flags
    & (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe') @args
    if($LASTEXITCODE -ne 0 -or (Select-String -LiteralPath $log -Pattern 'Result=\{Fail\}|Fatal error|PARIS_REFERENCE_INVALID|PARIS_REFERENCE_MISSING' -Quiet)){throw ('Native automation failed '+$group.Name)}
    foreach($name in $group.Tests){if(-not(Select-String -LiteralPath $log -Pattern ('Result=\{Success\}.*Name=\{'+$name+'\}') -Quiet)){throw ('Test did not complete '+$name)}}
}
