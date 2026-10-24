param([string]$EngineRoot='D:\Epic Games\UE_5.8',[switch]$LegacyJSON,[switch]$NoRenderCache,[switch]$Photoreal,[switch]$NoScannedFacade,[switch]$DoorDetail,[switch]$VirginDetail,[switch]$NoNCStatues,[switch]$SimplePeople)
$ErrorActionPreference='Stop'
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$log=Join-Path (Split-Path $project) 'Saved\paris-twin-automation.log'
$argsGIS=@($project,'-game','-ParisTwin','-unattended','-nullrhi','-nosound','-nosplash','-ExecCmds=Automation RunTests ParisDigitalTwin.Live','-TestExit=Automation Test Queue Empty',"-abslog=$log",'-stdout','-UTF8Output')
if($LegacyJSON){$argsGIS+='-ParisTwinLegacyJSON'}
if($NoRenderCache){$argsGIS+='-ParisTwinNoRenderCache'}
if($Photoreal){$argsGIS+=@('-ParisPhotoreal','-CustomConfig=ParisPhotoreal')}
if($NoScannedFacade){$argsGIS+='-ParisTwinNoScannedFacade'}
if($DoorDetail){$argsGIS+='-ParisTwinDoorDetail'}
if($VirginDetail){$argsGIS+='-ParisTwinVirginDetail'}
if($NoNCStatues){$argsGIS+='-ParisTwinNoNCStatues'}
if($SimplePeople){$argsGIS+='-ParisTwinSimplePeople'}
& $editor @argsGIS
if($LASTEXITCODE -ne 0 -or (Select-String -LiteralPath $log -Pattern 'Result=\{Fail\}|Fatal error' -Quiet) -or -not(Select-String -LiteralPath $log -Pattern 'Result=\{Success\}.*SceneCollisionAndDebug' -Quiet)){throw 'GIS scene/selection/collision automation failed'}
foreach($test in @('CoordinateAgreement','SceneCollisionAndDebug','StreetInstancesAndQuality','WalkingAndPedestrians','TrafficAndMappedProps','BusinessesAndTerraces','RuntimePacketSafety','CafeVisitLifecycle','WalkingGraphRouting','CafeSeatingLifecycle','LocalSocialInteraction','SurfaceMaterialsAndDetails','RenderCacheParityAndModes','PhotographicSurfaceBindings','PhotoEnvironmentAndCameraSwitching','PhotoDetailAssetsAndFallback','PhotoBridgeDeckHeight','CoveredTerrainDisplayAndCollision','FrontageGeometryAndFallback')){
    if(-not(Select-String -LiteralPath $log -Pattern ('Result=\{Success\}.*Name=\{'+$test+'\}') -Quiet)){throw "GIS automation test did not succeed: $test"}
}
if(-not(Select-String -LiteralPath $log -Pattern 'Result=\{Success\}.*Name=\{ObservedFacadeAndFallback\}' -Quiet)){throw 'Observed facade/fallback automation did not succeed'}
if($Photoreal -and -not $NoScannedFacade){
    $scan=Get-Content -LiteralPath (Join-Path (Split-Path $project) 'Content\Data\paris-notredame-scan.json') -Raw | ConvertFrom-Json
    $finish=$scan.material_calibration.detail_finish
    if($finish -notmatch 'white_plaster_02' -or $finish -notmatch 'normal weight 0\.16' -or $finish -notmatch 'roughness weight 0\.38'){
        throw 'Photoreal scan is missing the verified CC0 micro-normal/roughness finish'
    }
}
if(-not(Select-String -LiteralPath $log -Pattern 'Result=\{Success\}.*Name=\{ScannedVirginAndFallback\}' -Quiet)){throw 'Scanned Virgin/fallback automation did not succeed'}
if(-not(Select-String -LiteralPath $log -Pattern 'Result=\{Success\}.*Name=\{RealisticPedestrianVisuals\}' -Quiet)){throw 'Realistic pedestrian/fallback automation did not succeed'}
if(-not(Select-String -LiteralPath $log -Pattern 'Result=\{Success\}.*Name=\{ProtagonistWalkRun\}' -Quiet)){throw 'Protagonist walking/running automation did not succeed'}
