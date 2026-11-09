param([string]$EngineRoot='D:\Epic Games\UE_5.8')
$ErrorActionPreference='Stop'
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$log=Join-Path (Split-Path $project) 'Saved\paris-weathering-automation.log'
$names=@('LocalWeatheringAndSkyPresets','NightLightingAndDayRestoration','PhotoEnvironmentAndCameraSwitching','RainLifecycleAndShelter','CoveredTerrainDisplayAndCollision','SpatialSoundscapeAndSharedMute','PhotographicSurfaceBindings','SurfaceMaterialsAndDetails','MinimapGeographyAndPlayerTracking','FestivalModeAndRestoration')
$tests=(($names | ForEach-Object {'ParisDigitalTwin.Live.'+$_}) -join '+')
& (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe') $project -game -ParisTwin -ParisPhotoreal -CustomConfig=ParisPhotoreal -nullrhi -unattended -nosplash ('-ExecCmds=Automation RunTests '+$tests) '-TestExit=Automation Test Queue Empty' ('-abslog='+$log) -stdout -UTF8Output
if($LASTEXITCODE -ne 0 -or (Select-String -LiteralPath $log -Pattern 'Result=\{Fail\}|Fatal error' -Quiet)){throw 'Paris weathering automation failed'}
foreach($name in $names){if(-not(Select-String -LiteralPath $log -Pattern ('Result=\{Success\}.*Name=\{'+$name+'\}') -Quiet)){throw ('Test did not complete: '+$name)}}
