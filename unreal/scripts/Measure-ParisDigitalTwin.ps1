param(
    [string]$EngineRoot='D:\Epic Games\UE_5.8',
    [ValidateSet('Overview','Street','NotreDame','WalkFirst','WalkThird','Traffic','Cafe','Routes','Seating','Materials','Realism','Front','Riverside','PhotoStreet','WindowDetail','EntryDetail','PortalDetail','DoorDetail','VirginDetail')][string]$View='Overview',
    [ValidateSet('Low','Medium','High')][string]$Quality='Medium',
    [ValidateRange(10,120)][int]$Duration=20,
    [string]$ReportPath='',
    [ValidateRange(1,120)][int]$CaptureAfter=8,
    [switch]$LegacyJSON,
    [switch]$FullPeople,
    [switch]$SimplePeople,
    [switch]$PeopleView,
    [ValidateRange(0,159)][int]$PeopleIndex=0,
    [switch]$FlatMaterials,
    [switch]$ProceduralSurfaces,
    [switch]$NoShadows,
    [switch]$NoStreetDetails,
    [switch]$ProfileGPU,
    [switch]$NoRenderCache,
    [switch]$Unlit,
    [switch]$Photoreal,
    [switch]$NoPhotoNature,
    [switch]$NoArchitecture,
    [switch]$NoScannedFacade,
    [switch]$NoNCStatues,
    [switch]$NoPhotoStreet,
    [switch]$NoGroundCutout,
    [switch]$NoFrontages,
    [switch]$CleanFrame,
    [ValidateRange(640,3840)][int]$Width=1280,
    [ValidateRange(360,2160)][int]$Height=720,
    [string]$ScreenshotPath=''
)
$ErrorActionPreference='Stop'
if($CaptureAfter -ge $Duration+5){throw 'CaptureAfter must be before the benchmark exit time (Duration + 5s warmup)'}
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$saved=Join-Path (Split-Path $project) 'Saved'
$editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$native=Join-Path (Split-Path $project) 'Binaries\Win64\UnrealEditor-AIWorld.dll'
$newestSource=Get-ChildItem -LiteralPath (Join-Path (Split-Path $project) 'Source') -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if(-not(Test-Path -LiteralPath $native) -or $newestSource.LastWriteTime -gt (Get-Item -LiteralPath $native).LastWriteTime){throw 'Native code changed; run Build-AIWorldUE.ps1 before measuring'}
$log=Join-Path $saved 'paris-twin-measure.log'
$performance=Join-Path $saved 'paris-twin-performance.json'
$shot=Join-Path $saved 'Screenshots\paris-twin.png'
$suffix=if($LegacyJSON){'-legacy'}else{''}
if($FullPeople){$suffix+='-fullpeople'}
if($FlatMaterials){$suffix+='-flat'}
if(-not $ReportPath){$ReportPath=Join-Path $repo "docs\paris-twin-phase7-seating-$($View.ToLower())$suffix-performance.json"}
$reportFolder=Split-Path $ReportPath
New-Item -ItemType Directory -Path $reportFolder -Force | Out-Null
$commands='t.MaxFPS 0,r.VSync 0'
$screenPercentage=@{Low=65;Medium=80;High=100}[$Quality]
$commands+=",r.ScreenPercentage $screenPercentage"
$commands+=',r.Shadow.Virtual.NonNanite.IncludeInCoarsePages'
if($CleanFrame){$commands+=',ShowHUD'}
if($Unlit){$commands+=',viewmode unlit'}else{$commands+=',viewmode lit'}
if($ProfileGPU){$commands+=',stat unit,stat gpu'}
$arguments=@( ('"'+$project+'"'),'-game','-ParisTwin','-dx11','-windowed','-ForceRes',('-ResX='+$Width),('-ResY='+$Height),'-RenderOffscreen','-unattended','-nosound','-NoSplash',
    '-ParisTwinCapture','-ParisTwinWaitForAssets',"-ParisTwinCaptureAfter=$CaptureAfter","-ParisTwinBenchmark=$Duration",'-ParisTwinExit',('-ExecCmds="'+$commands+'"'),
    ('-ParisTwinQuality='+@{Low=0;Medium=1;High=2}[$Quality]),('-abslog="'+$log+'"'))
if($Photoreal){$arguments=@($arguments | Where-Object {$_ -ne '-dx11'});$arguments+=@('-dx12','-sm6','-CustomConfig=ParisPhotoreal','-ParisPhotoreal')}
if($View -in @('Front','Riverside','PhotoStreet','WindowDetail','EntryDetail','PortalDetail','DoorDetail','VirginDetail')){$arguments+=('-ParisTwinPhotoCamera='+@{Front='Camera_NotreDame_Front';Riverside='Camera_NotreDame_Riverside';PhotoStreet='Camera_Paris_Street';WindowDetail='Camera_Paris_Street';EntryDetail='Camera_Paris_Street';PortalDetail='Camera_NotreDame_Front';DoorDetail='Camera_NotreDame_Front';VirginDetail='Camera_NotreDame_Front'}[$View])}
if($View -eq 'WindowDetail'){$arguments+='-ParisTwinWindowDetail'}
if($View -eq 'PortalDetail'){$arguments+='-ParisTwinPortalDetail'}
if($View -eq 'DoorDetail'){$arguments+='-ParisTwinDoorDetail'}
if($View -eq 'VirginDetail'){$arguments+='-ParisTwinVirginDetail'}
if($NoNCStatues){$arguments+='-ParisTwinNoNCStatues'}
if($View -eq 'EntryDetail'){$arguments+='-ParisTwinEntryDetail'}
if($LegacyJSON){$arguments+='-ParisTwinLegacyJSON'}
if($FullPeople){$arguments+='-ParisTwinFullPeople'}
if($SimplePeople){$arguments+='-ParisTwinSimplePeople'}
if($PeopleView){$arguments+=@('-ParisTwinPeopleView',('-ParisTwinPeopleIndex='+$PeopleIndex))}
if($FlatMaterials){$arguments+='-ParisTwinFlatMaterials'}
if($ProceduralSurfaces){$arguments+='-ParisTwinProceduralSurfaces'}
if($NoShadows){$arguments+='-ParisTwinNoShadows'}
if($NoStreetDetails){$arguments+='-ParisTwinNoStreetDetails'}
if($ProfileGPU){$arguments+='-ParisTwinProfileGPU'}
if($NoRenderCache){$arguments+='-ParisTwinNoRenderCache'}
if($NoPhotoNature){$arguments+='-ParisTwinNoPhotoNature'}
if($NoArchitecture){$arguments+='-ParisTwinNoArchitecture'}
if($NoScannedFacade){$arguments+='-ParisTwinNoScannedFacade'}
if($NoPhotoStreet){$arguments+='-ParisTwinNoPhotoStreet'}
if($NoGroundCutout){$arguments+='-ParisTwinNoGroundCutout'}
if($NoFrontages){$arguments+='-ParisTwinNoFrontages'}
if($View -eq 'Materials'){$arguments+='-ParisTwinCafeView';$arguments+='-ParisTwinSurfaceView'}
if($View -eq 'Realism'){$arguments+=@('-ParisTwinCafeView','-ParisTwinSurfaceView','-ParisTwinStreetPhoto')}
if($View -eq 'Seating'){$arguments+='-ParisTwinCafeView';$arguments+='-ParisTwinSeatingView'}
if($View -eq 'Cafe'){$arguments+='-ParisTwinCafeView'}
if($View -eq 'Routes'){$arguments+='-ParisTwinCafeView';$arguments+='-ParisTwinRoutes'}
if($View -eq 'Traffic'){$arguments+='-ParisTwinTrafficView'}
if($View -eq 'Street'){$arguments+='-ParisTwinEye'}
if($View -eq 'WalkFirst'){$arguments+='-ParisTwinWalk'}
if($View -eq 'WalkThird'){$arguments+='-ParisTwinThirdPerson'}
if($View -eq 'NotreDame'){$arguments+='-ParisTwinLandmark=1'}
$started=Get-Date
$mutex=[Threading.Mutex]::new($false,'Local\AIWorldParisBenchmark')
$ownsMutex=$false
try {
    try {$ownsMutex=$mutex.WaitOne(0)}catch [Threading.AbandonedMutexException]{$ownsMutex=$true}
    if(-not $ownsMutex){throw 'Another Paris benchmark is running; shared engine outputs require sequential measurement'}
$otherEditors=@(Get-CimInstance Win32_Process -Filter "Name='UnrealEditor.exe'" | ForEach-Object {
    [pscustomobject]@{process_id=$_.ProcessId;game=([bool]($_.CommandLine -match '(?i)(?:^|\s)-game(?:\s|$)'));offscreen=([bool]($_.CommandLine -match '(?i)-RenderOffscreen'))}
})
$process=Start-Process -FilePath $editor -ArgumentList $arguments -WindowStyle Hidden -PassThru
if(-not $process.WaitForExit(600000)){
    if(-not $process.HasExited){Stop-Process -Id $process.Id}
    throw 'Paris benchmark did not finish within ten minutes; its owned helper process was stopped'
}
if($process.ExitCode -ne 0 -or -not(Test-Path -LiteralPath $performance) -or (Get-Item -LiteralPath $performance).LastWriteTime -lt $started){throw 'Paris benchmark failed or did not produce a fresh report'}
if(Select-String -LiteralPath $log -Pattern 'Fatal error|Assertion failed|missing usage flag (?:InstancedStaticMeshes|Nanite)|CPU data not available on selected LOD|Failed to compile Material' -Quiet){throw 'Unreal reported a benchmark mesh/material error'}
$result=Get-Content -LiteralPath $performance -Raw | ConvertFrom-Json
if(-not(Test-Path -LiteralPath $shot) -or (Get-Item -LiteralPath $shot).LastWriteTime -lt $started){throw 'No fresh rendered screenshot was produced'}
$header=[byte[]]::new(24);$imageStream=[IO.File]::OpenRead($shot)
try{if($imageStream.Read($header,0,24) -ne 24){throw 'Incomplete screenshot header'}}finally{$imageStream.Dispose()}
if($header[0] -ne 137 -or $header[1] -ne 80 -or $header[2] -ne 78 -or $header[3] -ne 71){throw 'Rendered screenshot is not a PNG'}
$actualWidth=([int]$header[16] -shl 24) -bor ([int]$header[17] -shl 16) -bor ([int]$header[18] -shl 8) -bor [int]$header[19]
$actualHeight=([int]$header[20] -shl 24) -bor ([int]$header[21] -shl 16) -bor ([int]$header[22] -shl 8) -bor [int]$header[23]
if($actualWidth -ne $Width -or $actualHeight -ne $Height){throw "Rendered resolution was clamped to ${actualWidth}x${actualHeight}; requested ${Width}x${Height}"}
if(-not $result.benchmark_wait_for_assets -or $result.benchmark_assets_pending -ne 0){throw 'Benchmark started before asset/shader preparation completed'}
if($Photoreal -and ($result.rhi -ne 'D3D12' -or $result.shader_feature_level -ne 'SM6' -or $result.gi_method -ne 1 -or $result.baked_visual_components -lt 1)){throw 'Photoreal renderer or offline visual assets were not applied'}
if($Photoreal -and ($null -eq $result.baked_bounds_max_error_cm -or $result.baked_bounds_max_error_cm -gt .1 -or $result.baked_palette_mismatch_samples -gt 0)){throw 'Baked visual bounds or vertex colours differ from the source GIS mesh; inspect the render cache'}
$expectedScan=if($Photoreal -and -not $NoArchitecture -and -not $NoScannedFacade -and (Test-Path -LiteralPath (Join-Path (Split-Path $project) 'Content\Data\paris-notredame-scan.json'))){1}else{0}
if($result.scanned_facade_components -ne $expectedScan -or ($expectedScan -eq 1 -and $result.scanned_facade_nanite -ne 1)){throw 'Observed facade mode or actual Nanite data was not applied'}
$visibleScan=if($Quality -eq 'Low' -or $FlatMaterials){0}else{$expectedScan}
if($result.scanned_facade_visible -ne $visibleScan){throw 'Observed facade visibility did not match the requested quality'}
if($Photoreal -and -not $LegacyJSON){
    $expectedFrontages=if($NoFrontages){0}else{4}
    if($result.frontage_components -ne $expectedFrontages){throw 'Requested frontage mode was not applied'}
    $visibleFrontages=if($Quality -eq 'Low' -or $FlatMaterials){0}else{$expectedFrontages}
    if($result.frontage_visible -ne $visibleFrontages){throw 'Requested frontage quality/visibility was not applied'}
}
if($View -in @('Front','Riverside','PhotoStreet','WindowDetail','EntryDetail','PortalDetail','DoorDetail','VirginDetail') -and $result.active_photo_camera -notmatch '^Camera_'){throw 'Named photo camera did not activate'}
if($result.virgin_detail_view -ne ($View -eq 'VirginDetail')){throw 'Requested Virgin inspection camera was not applied'}
if($result.door_detail_view -ne ($View -eq 'DoorDetail')){throw 'Requested door inspection camera was not applied'}
if($result.window_detail_view -ne ($View -eq 'WindowDetail')){throw 'Requested window inspection camera was not applied'}
if($result.shadows_disabled -ne [bool]$NoShadows -or $result.street_details -ne (-not $NoStreetDetails)){throw 'Requested rendering diagnostic options were not applied'}
if($null -eq $result.render_cache_components -or ($NoRenderCache -and $result.render_cache_components -ne 0) -or (-not $NoRenderCache -and $result.render_cache_components -lt 1)){throw 'Requested render cache mode was not applied; check the native build'}
if($result.detailed_surfaces -ne (-not $FlatMaterials -and $Quality -ne 'Low')){throw 'Requested surface mode was not applied'}
if($result.photographic_surfaces -ne (-not $ProceduralSurfaces -and -not $FlatMaterials -and $Quality -ne 'Low')){throw 'Requested photographic material mode was not applied'}
if($View -in @('Traffic','Cafe','Routes','Seating','Materials','Realism') -and -not $result.camera_eye){throw 'Inspection did not find an unobstructed eye-level camera'}
if($View -in @('WalkFirst','WalkThird') -and -not $result.walking){throw 'Requested walking view did not become active'}
$result | Add-Member -NotePropertyName 'render_offscreen' -NotePropertyValue $true
$result | Add-Member -NotePropertyName 'people_inspection' -NotePropertyValue ([bool]$PeopleView)
$result | Add-Member -NotePropertyName 'people_inspection_index' -NotePropertyValue $PeopleIndex
$result | Add-Member -NotePropertyName 'simple_people_requested' -NotePropertyValue ([bool]$SimplePeople)
$result | Add-Member -NotePropertyName 'clean_frame' -NotePropertyValue ([bool]$CleanFrame)
$coarseValue=Select-String -LiteralPath $log -Pattern 'r\.Shadow\.Virtual\.NonNanite\.IncludeInCoarsePages = "([01])"' | Select-Object -Last 1
if($coarseValue){$result | Add-Member -NotePropertyName 'non_nanite_coarse_pages' -NotePropertyValue ([int]$coarseValue.Matches[0].Groups[1].Value)}
$result | Add-Member -NotePropertyName 'screen_percentage' -NotePropertyValue $screenPercentage
$result | Add-Member -NotePropertyName 'output_width' -NotePropertyValue $actualWidth
$result | Add-Member -NotePropertyName 'output_height' -NotePropertyValue $actualHeight
$result | Add-Member -NotePropertyName 'resolution_verified_from_png' -NotePropertyValue $true
$result | Add-Member -NotePropertyName 'requested_view_mode' -NotePropertyValue $(if($Unlit){'Unlit diagnostic'}else{'Lit'})
$result | Add-Member -NotePropertyName 'gpu_profile_overlay' -NotePropertyValue ([bool]$ProfileGPU)
$result | Add-Member -NotePropertyName 'other_unreal_instances_at_start' -NotePropertyValue $otherEditors
$otherAtEnd=@(Get-CimInstance Win32_Process -Filter "Name='UnrealEditor.exe'" | Where-Object ProcessId -ne $process.Id | ForEach-Object {
    [pscustomobject]@{process_id=$_.ProcessId;game=([bool]($_.CommandLine -match '(?i)(?:^|\s)-game(?:\s|$)'));offscreen=([bool]($_.CommandLine -match '(?i)-RenderOffscreen'))}
})
$result | Add-Member -NotePropertyName 'other_unreal_instances_at_end' -NotePropertyValue $otherAtEnd
$result | Add-Member -NotePropertyName 'requested_view' -NotePropertyValue $View
$result | Add-Member -NotePropertyName 'duration_seconds' -NotePropertyValue $Duration
$result | Add-Member -NotePropertyName 'capture_after_seconds' -NotePropertyValue $CaptureAfter
$result | Add-Member -NotePropertyName 'warmup_seconds' -NotePropertyValue 5
$result | Add-Member -NotePropertyName 'run_utc' -NotePropertyValue $started.ToUniversalTime().ToString('o')
$result | Add-Member -NotePropertyName 'engine' -NotePropertyValue 'UE 5.8.3 Development Editor -game'
$result | Add-Member -NotePropertyName 'gpu' -NotePropertyValue ((Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join ', ')
$scene=Join-Path (Split-Path $project) 'Content\Data\paris-digital-twin.json'
$result | Add-Member -NotePropertyName 'scene_sha256' -NotePropertyValue ((Get-FileHash -LiteralPath $scene -Algorithm SHA256).Hash.ToLowerInvariant())
$result | Add-Member -NotePropertyName 'native_binary_sha256' -NotePropertyValue ((Get-FileHash -LiteralPath $native -Algorithm SHA256).Hash.ToLowerInvariant())
$result | Add-Member -NotePropertyName 'nc_statues_disabled' -NotePropertyValue ([bool]$NoNCStatues)
$statueManifest=Join-Path (Split-Path $project) 'Content\Data\paris-notredame-statue.json'
if(Test-Path -LiteralPath $statueManifest){
    $statueDescription=Get-Content -LiteralPath $statueManifest -Raw | ConvertFrom-Json
    $result | Add-Member -NotePropertyName 'available_statue_manifest_sha256' -NotePropertyValue ((Get-FileHash -LiteralPath $statueManifest -Algorithm SHA256).Hash.ToLowerInvariant())
    $result | Add-Member -NotePropertyName 'available_statue_geometry_sha256' -NotePropertyValue $statueDescription.geometry_sha256
}
$architectureManifest=Join-Path (Split-Path $project) 'Content\Data\paris-photo-architecture.json'
if(Test-Path -LiteralPath $architectureManifest){
    $architectureDescription=Get-Content -LiteralPath $architectureManifest -Raw | ConvertFrom-Json
    $result | Add-Member -NotePropertyName 'available_architecture_manifest_sha256' -NotePropertyValue ((Get-FileHash -LiteralPath $architectureManifest -Algorithm SHA256).Hash.ToLowerInvariant())
    $result | Add-Member -NotePropertyName 'available_architecture_revision' -NotePropertyValue $architectureDescription.detail_revision
}
$scanManifest=Join-Path (Split-Path $project) 'Content\Data\paris-notredame-scan.json'
if(Test-Path -LiteralPath $scanManifest){
    $scanDescription=Get-Content -LiteralPath $scanManifest -Raw | ConvertFrom-Json
    $result | Add-Member -NotePropertyName 'available_scan_manifest_sha256' -NotePropertyValue ((Get-FileHash -LiteralPath $scanManifest -Algorithm SHA256).Hash.ToLowerInvariant())
    $result | Add-Member -NotePropertyName 'available_scan_geometry_sha256' -NotePropertyValue $scanDescription.geometry_sha256
    $result | Add-Member -NotePropertyName 'available_scan_revision' -NotePropertyValue $scanDescription.surface.revision
}
$result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $ReportPath -Encoding utf8
if(-not(Test-Path -LiteralPath $shot) -or (Get-Item -LiteralPath $shot).LastWriteTime -lt $started){throw 'The run did not produce a fresh screenshot; inspection may not have found a clear camera'}
if(Test-Path -LiteralPath $shot){
    if((Get-Item -LiteralPath $shot).LastWriteTime -ge $started){
        $screenshots=Join-Path $reportFolder 'screenshots';New-Item -ItemType Directory -Path $screenshots -Force | Out-Null
        if(-not $ScreenshotPath){$ScreenshotPath=Join-Path $screenshots (([IO.Path]::GetFileNameWithoutExtension($ReportPath) -replace '-performance$','')+'.png')}
        New-Item -ItemType Directory -Path (Split-Path $ScreenshotPath) -Force | Out-Null
        Copy-Item -LiteralPath $shot -Destination $ScreenshotPath
    }
}
if($ProfileGPU){Select-String -LiteralPath $log -Pattern 'LogRHI: Display:' | ForEach-Object {$_.Line} | Set-Content -LiteralPath ([IO.Path]::ChangeExtension($ReportPath,'.gpu.log')) -Encoding utf8}
Write-Output "Saved $View / $Quality benchmark: $ReportPath"
Write-Output "FPS $($result.fps) | P95 $($result.frame_p95_ms)ms"
}finally{if($ownsMutex){$mutex.ReleaseMutex()};$mutex.Dispose()}
