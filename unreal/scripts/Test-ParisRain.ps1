param([string]$EngineRoot='D:\Epic Games\UE_5.8')
$ErrorActionPreference='Stop'
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$log=Join-Path (Split-Path $project) 'Saved\paris-rain-automation.log'
$tests='ParisDigitalTwin.Live.RainLifecycleAndShelter+ParisDigitalTwin.Live.PhotoEnvironmentAndCameraSwitching'
# Keep the audio device enabled: resource binding alone cannot prove playback.
& $editor $project -game -ParisTwin -ParisPhotoreal -CustomConfig=ParisPhotoreal -nullrhi -unattended -nosplash ('-ExecCmds=Automation RunTests '+$tests) '-TestExit=Automation Test Queue Empty' ('-abslog='+$log) -stdout -UTF8Output
if($LASTEXITCODE -ne 0 -or (Select-String -LiteralPath $log -Pattern 'Result=\{Fail\}|Fatal error' -Quiet)){throw 'Paris rain automation failed'}
foreach($name in @('RainLifecycleAndShelter','PhotoEnvironmentAndCameraSwitching')){
    if(-not(Select-String -LiteralPath $log -Pattern ('Result=\{Success\}.*Name=\{'+$name+'\}') -Quiet)){throw ('Rain check did not complete: '+$name)}
}
