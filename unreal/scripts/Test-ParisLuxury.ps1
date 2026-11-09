param([string]$EngineRoot='D:\Epic Games\UE_5.8')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
& (Join-Path $repo 'gis\.venv\Scripts\python.exe') -m unittest discover -s (Join-Path $PSScriptRoot 'tests') -p 'test_paris_luxury.py'
if($LASTEXITCODE -ne 0){throw 'Luxury GIS validation failed'}
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$log=Join-Path (Split-Path $project) 'Saved\paris-luxury-automation.log'
$names=@('LuxuryStreetAndWalkingClearance','MappedMorrisAndStreetSigns','CoveredTerrainDisplayAndCollision','NightLightingAndDayRestoration','RainLifecycleAndShelter','SurfaceMaterialsAndDetails','RealisticPedestrianVisuals','StreetRealismRenderingPolicy','FestivalModeAndRestoration','MinimapGeographyAndPlayerTracking','LocalWeatheringAndSkyPresets')
$tests=(($names | ForEach-Object {'ParisDigitalTwin.Live.'+$_}) -join '+')
& (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe') $project -game -ParisTwin -ParisPhotoreal -CustomConfig=ParisPhotoreal -nullrhi -unattended -nosplash ('-ExecCmds=Automation RunTests '+$tests) '-TestExit=Automation Test Queue Empty' ('-abslog='+$log) -stdout -UTF8Output
if($LASTEXITCODE -ne 0 -or (Select-String -LiteralPath $log -Pattern 'Result=\{Fail\}|Fatal error' -Quiet)){throw 'Paris luxury automation failed'}
foreach($name in $names){if(-not(Select-String -LiteralPath $log -Pattern ('Result=\{Success\}.*Name=\{'+$name+'\}') -Quiet)){throw ('Test did not complete: '+$name)}}
