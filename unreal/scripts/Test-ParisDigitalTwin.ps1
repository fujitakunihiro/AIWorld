param([string]$EngineRoot='D:\Epic Games\UE_5.8',[switch]$LegacyJSON,[switch]$NoRenderCache,[switch]$Photoreal,[switch]$NoScannedFacade)
$ErrorActionPreference='Stop'
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$log=Join-Path (Split-Path $project) 'Saved\paris-twin-automation.log'
$argsGIS=@($project,'-game','-ParisTwin','-unattended','-nullrhi','-nosound','-nosplash','-ExecCmds=Automation RunTests ParisDigitalTwin.Live','-TestExit=Automation Test Queue Empty',"-abslog=$log",'-stdout','-UTF8Output')
if($LegacyJSON){$argsGIS+='-ParisTwinLegacyJSON'}
if($NoRenderCache){$argsGIS+='-ParisTwinNoRenderCache'}
if($Photoreal){$argsGIS+=@('-ParisPhotoreal','-CustomConfig=ParisPhotoreal')}
if($NoScannedFacade){$argsGIS+='-ParisTwinNoScannedFacade'}
& $editor @argsGIS
if($LASTEXITCODE -ne 0 -or (Select-String -LiteralPath $log -Pattern 'Result=\{Fail\}|Fatal error' -Quiet) -or -not(Select-String -LiteralPath $log -Pattern 'Result=\{Success\}.*SceneCollisionAndDebug' -Quiet)){throw 'GIS scene/selection/collision automation failed'}
foreach($test in @('CoordinateAgreement','SceneCollisionAndDebug','StreetInstancesAndQuality','WalkingAndPedestrians','TrafficAndMappedProps','BusinessesAndTerraces','RuntimePacketSafety','CafeVisitLifecycle','WalkingGraphRouting','CafeSeatingLifecycle','LocalSocialInteraction','SurfaceMaterialsAndDetails','RenderCacheParityAndModes','PhotographicSurfaceBindings','PhotoEnvironmentAndCameraSwitching','PhotoDetailAssetsAndFallback','PhotoBridgeDeckHeight','CoveredTerrainDisplayAndCollision','FrontageGeometryAndFallback')){
    if(-not(Select-String -LiteralPath $log -Pattern ('Result=\{Success\}.*Name=\{'+$test+'\}') -Quiet)){throw "GIS automation test did not succeed: $test"}
}
if(-not(Select-String -LiteralPath $log -Pattern 'Result=\{Success\}.*Name=\{ObservedFacadeAndFallback\}' -Quiet)){throw 'Observed facade/fallback automation did not succeed'}
