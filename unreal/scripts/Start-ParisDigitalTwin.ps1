param([string]$EngineRoot='D:\Epic Games\UE_5.8',[switch]$Download,[switch]$Refresh,[switch]$Build,[switch]$Eye,[switch]$Capture,[ValidateRange(0,120)][double]$Benchmark=0,[switch]$ExitAfterBenchmark,[switch]$NoShadows,[switch]$Footprints,[switch]$Issues,[string]$Config='',[switch]$DownloadBuildings,[ValidateRange(0,3)][int]$Landmark=0,[switch]$DownloadTerrain,[ValidateSet('Low','Medium','High')][string]$Quality='Medium',[switch]$NoStreetDetails,[switch]$Walk,[switch]$ThirdPerson,[switch]$NoPeople,[switch]$NoTraffic,[switch]$TrafficView,[switch]$CafeView,[switch]$LegacyJSON,[switch]$MaterialsView,[switch]$FlatMaterials,[switch]$NoRenderCache,[switch]$StreetPhotoView,[switch]$ProceduralSurfaces,[switch]$Photoreal,[switch]$PortalDetail,[switch]$NoScannedFacade,
    [switch]$EntryDetail,[switch]$DoorDetail,[switch]$VirginDetail,[switch]$NoNCStatues,[switch]$SimplePeople,[switch]$RiverView,[switch]$LegacyWater,[switch]$RoadView,[switch]$LegacyRoads,[ValidateSet('Front','Riverside','Street')][string]$PhotoCamera='')
$ErrorActionPreference='Stop'
if($RiverView){$Photoreal=$true;$PhotoCamera='Riverside'}
if($RoadView){$Photoreal=$true;$PhotoCamera='Street'}
if($EntryDetail){$Photoreal=$true;$PhotoCamera='Street'}
if($PortalDetail){$Photoreal=$true;$PhotoCamera='Front'}
if($DoorDetail){$Photoreal=$true;$PhotoCamera='Front'}
if($VirginDetail){$Photoreal=$true;$PhotoCamera='Front'}
if($StreetPhotoView -and -not $PSBoundParameters.ContainsKey('Quality')){$Quality='High'}
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$gisOptions=@()
if($Config){$gisOptions=@('--config',(Resolve-Path -LiteralPath $Config).Path)}
$python=Join-Path $repo 'gis\.venv\Scripts\python.exe'
if(-not(Test-Path -LiteralPath $python)){& py -3.12 -m venv (Join-Path $repo 'gis\.venv');if($LASTEXITCODE -ne 0){throw 'Python 3.12 environment creation failed'}}
Push-Location -LiteralPath $repo
$previousPythonPath=$env:PYTHONPATH
$previousEncoding=$env:PYTHONIOENCODING
try {
    $env:PYTHONPATH=Join-Path $repo 'gis'
    $env:PYTHONIOENCODING='utf-8'
    & $python -m pip install --disable-pip-version-check -r gis/requirements.lock
    if($LASTEXITCODE -ne 0){throw 'Pinned GIS dependency install failed'}
    if($Download){$options=@('download');if($Refresh){$options+='--refresh'};& $python -m paris_twin @options @gisOptions;if($LASTEXITCODE -ne 0){throw 'GIS download failed'}}
    if($DownloadBuildings){$options=@('download-buildings');if($Refresh){$options+='--refresh'};& $python -m paris_twin @options @gisOptions;if($LASTEXITCODE -ne 0){throw 'IGN building acquisition failed'}}
    if($DownloadTerrain){$options=@('download-terrain');if($Refresh){$options+='--refresh'};& $python -m paris_twin @options @gisOptions;if($LASTEXITCODE -ne 0){throw 'IGN terrain acquisition failed'}}
    & $python -m paris_twin prepare --offline @gisOptions
    if($LASTEXITCODE -ne 0){throw 'Offline GIS generation failed; acquire raw data with -Download first'}
    & $python -m paris_twin validate --offline @gisOptions
    if($LASTEXITCODE -ne 0){throw 'GIS validation failed'}
}finally{$env:PYTHONPATH=$previousPythonPath;$env:PYTHONIOENCODING=$previousEncoding;Pop-Location}
$dll=Join-Path $repo 'unreal\AIWorld\Binaries\Win64\UnrealEditor-AIWorld.dll'
$newestSource=Get-ChildItem -LiteralPath (Join-Path $repo 'unreal\AIWorld\Source') -File -Recurse | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if($Build -or -not(Test-Path -LiteralPath $dll) -or $newestSource.LastWriteTime -gt (Get-Item -LiteralPath $dll).LastWriteTime){& (Join-Path $PSScriptRoot 'Build-AIWorldUE.ps1') -EngineRoot $EngineRoot;if($LASTEXITCODE -ne 0){throw 'Native build failed'}}
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
if($Photoreal){
    # Windows PowerShell 5.1 is very slow expanding millions of mesh numbers.
    # The launcher only needs the small readiness manifest from this packet.
    $packetPath=Join-Path (Split-Path $project) 'Content\Data\paris-digital-twin-runtime.json'
    $packetText=& $python -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8-sig')); print(json.dumps({k:d[k] for k in ('source_scene_sha256','baked_visuals')}))" $packetPath
    if($LASTEXITCODE -ne 0){throw 'Could not read the prepared GIS render manifest'}
    $packet=$packetText | ConvertFrom-Json
    $bakePath=Join-Path (Split-Path $project) 'Saved\paris-v2-bake-report.json'
    $ready=$false
    if(Test-Path -LiteralPath $bakePath){$bake=Get-Content -LiteralPath $bakePath -Raw | ConvertFrom-Json;$ready=($bake.source_scene_sha256 -eq $packet.source_scene_sha256 -and $bake.bake_recipe -eq 'static_gis_sdf_nanite_v3')}
    foreach($entry in $packet.baked_visuals.PSObject.Properties){
        $assetPath=Join-Path (Split-Path $project) ('Content\'+$entry.Value.asset.Substring(6)+'.uasset')
        if(-not(Test-Path -LiteralPath $assetPath)){$ready=$false}
    }
    foreach($file in @('Content\ParisPhotoreal\Nature\SM_ParisBroadleaf.uasset','Content\Data\paris-photo-architecture.json','Content\Data\paris-photo-street.json','Content\Materials\M_ParisGrassPhotographic.uasset','Content\Materials\M_ParisCastIron.uasset','Content\Materials\M_ParisLanternGlass.uasset','Content\Materials\M_ParisCathedralStone.uasset','Content\Materials\M_ParisPhotographicSky.uasset')){
        if(-not(Test-Path -LiteralPath (Join-Path (Split-Path $project) $file))){$ready=$false}
    }
    foreach($file in @('Content\Materials\M_ParisWood.uasset','Content\Textures\T_ParisPhotoWoodAlbedo.uasset','Content\Textures\T_ParisPhotoWoodNormal.uasset','Content\Textures\T_ParisPhotoWoodOrm.uasset')){
        if(-not(Test-Path -LiteralPath (Join-Path (Split-Path $project) $file))){$ready=$false}
    }
    $streetPath=Join-Path (Split-Path $project) 'Content\Data\paris-photo-street.json'
    if(Test-Path -LiteralPath $streetPath){
        $street=Get-Content -LiteralPath $streetPath -Raw | ConvertFrom-Json
        foreach($part in $street.objects){if(-not(Test-Path -LiteralPath (Join-Path (Split-Path $project) ('Content\'+$part.asset.Substring(6)+'.uasset')))){$ready=$false}}
    }
    $architecturePath=Join-Path (Split-Path $project) 'Content\Data\paris-photo-architecture.json'
    if(Test-Path -LiteralPath $architecturePath){
        $architecture=Get-Content -LiteralPath $architecturePath -Raw | ConvertFrom-Json
        if($architecture.detail_revision -ne 14){$ready=$false}
        foreach($part in $architecture.objects){if(-not(Test-Path -LiteralPath (Join-Path (Split-Path $project) ('Content\'+$part.asset.Substring(6)+'.uasset')))){$ready=$false}}
    }
    $scanPath=Join-Path (Split-Path $project) 'Content\Data\paris-notredame-scan.json'
    if(-not $NoScannedFacade -and (Test-Path -LiteralPath $scanPath)){
        $scan=Get-Content -LiteralPath $scanPath -Raw | ConvertFrom-Json
        if($scan.surface.revision -ne 14){$ready=$false}
        $scanAssets=@($scan.asset,$scan.surface_material)+@($scan.underlays.PSObject.Properties | ForEach-Object {$_.Value})
        foreach($texture in $scan.textures.PSObject.Properties){$scanAssets+=('/Game/ParisPhotoreal/NotreDameScan/T_NDScan_'+$texture.Name+'_'+$texture.Value.sha256.Substring(0,10))}
        foreach($asset in $scanAssets){if(-not $asset -or -not(Test-Path -LiteralPath (Join-Path (Split-Path $project) ('Content\'+($asset -split '\.')[0].Substring(6)+'.uasset')))){$ready=$false}}
    }
    $groundPath=Join-Path (Split-Path $project) 'Content\Data\paris-photo-ground.json'
    if(Test-Path -LiteralPath $groundPath){
        $ground=Get-Content -LiteralPath $groundPath -Raw | ConvertFrom-Json
        if($ground.source_scene_sha256 -ne $packet.source_scene_sha256 -or -not(Test-Path -LiteralPath (Join-Path (Split-Path $project) ('Content\'+$ground.asset.Substring(6)+'.uasset')))){$ready=$false}
    }else{$ready=$false}
    if(-not(Test-Path -LiteralPath (Join-Path (Split-Path $project) 'Content\Materials\M_ParisGroundPaving.uasset'))){$ready=$false}
    foreach($name in @('paris-photo-frontages.json')){
        $extraPath=Join-Path (Split-Path $project) ('Content\Data\'+$name)
        if(Test-Path -LiteralPath $extraPath){
            $extra=Get-Content -LiteralPath $extraPath -Raw | ConvertFrom-Json
            if($extra.source_scene_sha256 -ne $packet.source_scene_sha256 -or $extra.format -ne 'paris_inferred_frontages_v2' -or @($extra.objects).Count -ne 4){$ready=$false}
            $extraAssets=@($extra.objects)
            foreach($part in $extraAssets){if(-not(Test-Path -LiteralPath (Join-Path (Split-Path $project) ('Content\'+$part.asset.Substring(6)+'.uasset')))){$ready=$false}}
        }else{$ready=$false}
    }
    foreach($mat in @('M_ParisWindowGlass','M_ParisWindowPaintedWood','M_ParisAsphaltPhotographic')){if(-not(Test-Path -LiteralPath (Join-Path (Split-Path $project) ('Content\Materials\'+$mat+'.uasset')))){$ready=$false}}
    if(-not(Test-Path -LiteralPath (Join-Path (Split-Path $project) 'Saved\paris-nanite-materials.json'))){$ready=$false}
    if(-not $ready){& (Join-Path $PSScriptRoot 'Build-ParisPhotoreal.ps1') -EngineRoot $EngineRoot}
}
$editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
if($Photoreal){
    $naturePath=Join-Path (Split-Path $project) 'Content\Data\paris-nature.json'
    $natureReady=$false
    if(Test-Path -LiteralPath $naturePath){
        $nature=Get-Content -LiteralPath $naturePath -Raw | ConvertFrom-Json
        $natureReady=($nature.recipe -eq 'paris_tree_foliage_v2')
    }
    if(-not $natureReady){& (Join-Path $PSScriptRoot 'Build-ParisNature.ps1') -EngineRoot $EngineRoot}
    $waterPath=Join-Path (Split-Path $project) 'Content\Data\paris-water.json'
    $waterReady=$false
    if(Test-Path -LiteralPath $waterPath){
        $water=Get-Content -LiteralPath $waterPath -Raw | ConvertFrom-Json
        $waterReady=($water.source_scene_sha256 -eq $packet.source_scene_sha256 -and $water.recipe -eq 'seine_single_layer_v1')
        foreach($asset in @('Materials\M_SeineRiver.uasset','Materials\M_ParisQuayWet.uasset','Textures\T_SeineRippleNormal.uasset','Textures\T_SeineShoreDistance.uasset')){
            if(-not(Test-Path -LiteralPath (Join-Path (Split-Path $project) ('Content\'+$asset)))){$waterReady=$false}
        }
    }
    if(-not $waterReady){& (Join-Path $PSScriptRoot 'Build-ParisWater.ps1') -EngineRoot $EngineRoot}
    $roadPath=Join-Path (Split-Path $project) 'Content\Data\paris-road-detail.json'
    $roadReady=$false
    if(Test-Path -LiteralPath $roadPath){
        $road=Get-Content -LiteralPath $roadPath -Raw | ConvertFrom-Json
        $roadReady=($road.source_scene_sha256 -eq $packet.source_scene_sha256 -and $road.recipe -eq 'paris_road_finish_v1')
        foreach($asset in @('Materials\M_ParisRoadAsphalt.uasset','Materials\M_ParisRoadSidewalk.uasset','Materials\M_ParisRoadPaving.uasset','Materials\M_ParisRoadKerb.uasset','Materials\M_ParisRoadIron.uasset','Textures\T_ParisRoadEdge.uasset','Textures\T_ParisRoadAge.uasset')){
            if(-not(Test-Path -LiteralPath (Join-Path (Split-Path $project) ('Content\'+$asset)))){$roadReady=$false}
        }
        foreach($part in $road.objects){if(-not(Test-Path -LiteralPath (Join-Path (Split-Path $project) ('Content\'+$part.asset.Substring(6)+'.uasset')))){$roadReady=$false}}
    }
    if(-not $roadReady){& (Join-Path $PSScriptRoot 'Build-ParisRoads.ps1') -EngineRoot $EngineRoot}
}
if(($Walk -or $ThirdPerson) -and -not $SimplePeople){
    $peoplePath=Join-Path (Split-Path $project) 'Content\Data\paris-people.json'
    $heroReady=$false
    if(Test-Path -LiteralPath $peoplePath){
        $people=Get-Content -LiteralPath $peoplePath -Raw | ConvertFrom-Json
        $hero=@($people.avatars)[0]
        $heroReady=($people.schema_version -eq 1 -and $hero.mesh -and $hero.animations.idle -and $hero.animations.walk -and $hero.animations.run)
        foreach($reference in @($hero.mesh,$hero.skeleton,$hero.animations.idle,$hero.animations.walk,$hero.animations.run)){
            if(-not $reference -or -not(Test-Path -LiteralPath (Join-Path (Split-Path $project) ('Content\'+($reference -split '\.')[0].Substring(6)+'.uasset')))){$heroReady=$false}
        }
    }
    if(-not $heroReady){& (Join-Path $PSScriptRoot 'Build-ParisPeople.ps1') -EngineRoot $EngineRoot}
}
if(-not(Test-Path -LiteralPath $editor)){throw 'Unreal Engine is not installed at '+$EngineRoot}
$launchArgs=@( ('"'+$project+'"'),'-game','-ParisTwin','-dx11','-windowed','-ResX=1280','-ResY=720','-NoSplash')
if($Photoreal){$launchArgs=@($launchArgs | Where-Object {$_ -ne '-dx11'});$launchArgs+=@('-dx12','-sm6','-CustomConfig=ParisPhotoreal','-ParisPhotoreal')}
if($NoScannedFacade){$launchArgs+='-ParisTwinNoScannedFacade'}
if($PortalDetail){$launchArgs+="-ParisTwinPortalDetail"}
if($DoorDetail){$launchArgs+="-ParisTwinDoorDetail"}
if($VirginDetail){$launchArgs+="-ParisTwinVirginDetail"}
if($NoNCStatues){$launchArgs+="-ParisTwinNoNCStatues"}
if($EntryDetail){$launchArgs+='-ParisTwinEntryDetail'}
if($PhotoCamera){$launchArgs+=('-ParisTwinPhotoCamera='+@{Front='Camera_NotreDame_Front';Riverside='Camera_NotreDame_Riverside';Street='Camera_Paris_Street'}[$PhotoCamera])}
if($Eye){$launchArgs+='-ParisTwinEye'}
if($RiverView){$launchArgs+='-ParisTwinRiverView'}
if($LegacyWater){$launchArgs+='-ParisTwinLegacyWater'}
if($RoadView){$launchArgs+='-ParisTwinRoadView'}
if($LegacyRoads){$launchArgs+='-ParisTwinLegacyRoads'}
if($Walk){$launchArgs+='-ParisTwinWalk'}
if($ThirdPerson){$launchArgs+='-ParisTwinThirdPerson'}
if($NoPeople){$launchArgs+='-ParisTwinNoPeople'}
if($SimplePeople){$launchArgs+='-ParisTwinSimplePeople'}
if($NoTraffic){$launchArgs+='-ParisTwinNoTraffic'}
if($TrafficView){$launchArgs+='-ParisTwinTrafficView'}
if($CafeView){$launchArgs+='-ParisTwinCafeView'}
if($StreetPhotoView){$launchArgs+=@('-ParisTwinCafeView','-ParisTwinSurfaceView','-ParisTwinStreetPhoto')}
if($ProceduralSurfaces){$launchArgs+='-ParisTwinProceduralSurfaces'}
if($MaterialsView){$launchArgs+=@('-ParisTwinCafeView','-ParisTwinSurfaceView')}
if($FlatMaterials){$launchArgs+='-ParisTwinFlatMaterials'}
if($NoRenderCache){$launchArgs+='-ParisTwinNoRenderCache'}
if($LegacyJSON){$launchArgs+='-ParisTwinLegacyJSON'}
if($Landmark -gt 0){$launchArgs+="-ParisTwinLandmark=$Landmark"}
if($Footprints){$launchArgs+='-ParisTwinFootprints'}
if($Issues){$launchArgs+='-ParisTwinIssues'}
if($Capture){$launchArgs+='-ParisTwinCapture'}
if($NoShadows){$launchArgs+='-ParisTwinNoShadows'}
$launchArgs+=('-ParisTwinQuality='+@{Low=0;Medium=1;High=2}[$Quality])
$launchArgs+=('-ExecCmds="r.ScreenPercentage '+@{Low=65;Medium=80;High=100}[$Quality]+'"')
if($NoStreetDetails){$launchArgs+='-ParisTwinNoStreetDetails'}
if($Benchmark -gt 0){$launchArgs+="-ParisTwinBenchmark=$Benchmark"}
if($ExitAfterBenchmark){$launchArgs+='-ParisTwinExit'}
Start-Process -FilePath $editor -ArgumentList $launchArgs
