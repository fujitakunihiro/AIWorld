param([string]$EngineRoot='D:\Epic Games\UE_5.8')
$ErrorActionPreference='Stop'
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$log=Join-Path (Split-Path $project) 'Saved\paris-soundscape-automation.log'
$tests='ParisDigitalTwin.Live.SpatialSoundscapeAndSharedMute+ParisDigitalTwin.Live.NightLightingAndDayRestoration+ParisDigitalTwin.Live.PhotoEnvironmentAndCameraSwitching+ParisDigitalTwin.Live.RainLifecycleAndShelter'
& (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe') $project -game -ParisTwin -ParisPhotoreal -CustomConfig=ParisPhotoreal -nullrhi -unattended -nosplash ('-ExecCmds=Automation RunTests '+$tests) '-TestExit=Automation Test Queue Empty' ('-abslog='+$log) -stdout -UTF8Output
if($LASTEXITCODE -ne 0 -or (Select-String -LiteralPath $log -Pattern 'Result=\{Fail\}|Fatal error' -Quiet)){throw 'Paris soundscape automation failed'}
foreach($name in @('SpatialSoundscapeAndSharedMute','NightLightingAndDayRestoration','PhotoEnvironmentAndCameraSwitching','RainLifecycleAndShelter')){
    if(-not(Select-String -LiteralPath $log -Pattern ('Result=\{Success\}.*Name=\{'+$name+'\}') -Quiet)){throw ('Soundscape check did not complete: '+$name)}
}
