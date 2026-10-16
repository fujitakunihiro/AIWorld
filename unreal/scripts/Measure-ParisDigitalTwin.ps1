param(
    [string]$EngineRoot='D:\Epic Games\UE_5.8',
    [ValidateSet('Overview','Street','NotreDame','WalkFirst','WalkThird','Traffic','Cafe','Routes','Seating','Materials','Realism','Front','Riverside','PhotoStreet','WindowDetail','EntryDetail')][string]$View='Overview',
    [ValidateSet('Low','Medium','High')][string]$Quality='Medium',
    [ValidateRange(10,120)][int]$Duration=20,
    [string]$ReportPath='',
    [ValidateRange(1,120)][int]$CaptureAfter=8,
    [switch]$LegacyJSON,
    [switch]$FullPeople,
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
    [switch]$NoPhotoStreet,
    [switch]$NoGroundCutout,
    [switch]$NoFrontages,
    [switch]$CleanFrame,
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
$arguments=@( ('"'+$project+'"'),'-game','-ParisTwin','-dx11','-windowed','-ResX=1280','-ResY=720','-RenderOffscreen','-unattended','-nosound','-NoSplash',
    '-ParisTwinCapture','-ParisTwinWaitForAssets',"-ParisTwinCaptureAfter=$CaptureAfter","-ParisTwinBenchmark=$Duration",'-ParisTwinExit',('-ExecCmds="'+$commands+'"'),
    ('-ParisTwinQuality='+@{Low=0;Medium=1;High=2}[$Quality]),('-abslog="'+$log+'"'))
if($Photoreal){$arguments=@($arguments | Where-Object {$_ -ne '-dx11'});$arguments+=@('-dx12','-sm6','-CustomConfig=ParisPhotoreal','-ParisPhotoreal')}
if($View -in @('Front','Riverside','PhotoStreet','WindowDetail','EntryDetail')){$arguments+=('-ParisTwinPhotoCamera='+@{Front='Camera_NotreDame_Front';Riverside='Camera_NotreDame_Riverside';PhotoStreet='Camera_Paris_Street';WindowDetail='Camera_Paris_Street';EntryDetail='Camera_Paris_Street'}[$View])}
if($View -eq 'WindowDetail'){$arguments+='-ParisTwinWindowDetail'}
if($View -eq 'EntryDetail'){$arguments+='-ParisTwinEntryDetail'}
if($LegacyJSON){$arguments+='-ParisTwinLegacyJSON'}
if($FullPeople){$arguments+='-ParisTwinFullPeople'}
if($FlatMaterials){$arguments+='-ParisTwinFlatMaterials'}
if($ProceduralSurfaces){$arguments+='-ParisTwinProceduralSurfaces'}
if($NoShadows){$arguments+='-ParisTwinNoShadows'}
if($NoStreetDetails){$arguments+='-ParisTwinNoStreetDetails'}
if($ProfileGPU){$arguments+='-ParisTwinProfileGPU'}
if($NoRenderCache){$arguments+='-ParisTwinNoRenderCache'}
if($NoPhotoNature){$arguments+='-ParisTwinNoPhotoNature'}
if($NoArchitecture){$arguments+='-ParisTwinNoArchitecture'}
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
if(-not $result.benchmark_wait_for_assets -or $result.benchmark_assets_pending -ne 0){throw 'Benchmark started before asset/shader preparation completed'}
if($Photoreal -and ($result.rhi -ne 'D3D12' -or $result.shader_feature_level -ne 'SM6' -or $result.gi_method -ne 1 -or $result.baked_visual_components -lt 1)){throw 'Photoreal renderer or offline visual assets were not applied'}
if($Photoreal -and ($null -eq $result.baked_bounds_max_error_cm -or $result.baked_bounds_max_error_cm -gt .1 -or $result.baked_palette_mismatch_samples -gt 0)){throw 'Baked visual bounds or vertex colours differ from the source GIS mesh; inspect the render cache'}
if($Photoreal -and -not $LegacyJSON){
    $expectedFrontages=if($NoFrontages){0}else{4}
    if($result.frontage_components -ne $expectedFrontages){throw 'Requested frontage mode was not applied'}
    $visibleFrontages=if($Quality -eq 'Low' -or $FlatMaterials){0}else{$expectedFrontages}
    if($result.frontage_visible -ne $visibleFrontages){throw 'Requested frontage quality/visibility was not applied'}
}
if($View -in @('Front','Riverside','PhotoStreet','WindowDetail') -and $result.active_photo_camera -notmatch '^Camera_'){throw 'Named photo camera did not activate'}
if($result.window_detail_view -ne ($View -eq 'WindowDetail')){throw 'Requested window inspection camera was not applied'}
if($result.shadows_disabled -ne [bool]$NoShadows -or $result.street_details -ne (-not $NoStreetDetails)){throw 'Requested rendering diagnostic options were not applied'}
if($null -eq $result.render_cache_components -or ($NoRenderCache -and $result.render_cache_components -ne 0) -or (-not $NoRenderCache -and $result.render_cache_components -lt 1)){throw 'Requested render cache mode was not applied; check the native build'}
if($result.detailed_surfaces -ne (-not $FlatMaterials -and $Quality -ne 'Low')){throw 'Requested surface mode was not applied'}
if($result.photographic_surfaces -ne (-not $ProceduralSurfaces -and -not $FlatMaterials -and $Quality -ne 'Low')){throw 'Requested photographic material mode was not applied'}
if($View -in @('Traffic','Cafe','Routes','Seating','Materials','Realism') -and -not $result.camera_eye){throw 'Inspection did not find an unobstructed eye-level camera'}
if($View -in @('WalkFirst','WalkThird') -and -not $result.walking){throw 'Requested walking view did not become active'}
$result | Add-Member -NotePropertyName 'render_offscreen' -NotePropertyValue $true
$result | Add-Member -NotePropertyName 'clean_frame' -NotePropertyValue ([bool]$CleanFrame)
$coarseValue=Select-String -LiteralPath $log -Pattern 'r\.Shadow\.Virtual\.NonNanite\.IncludeInCoarsePages = "([01])"' | Select-Object -Last 1
if($coarseValue){$result | Add-Member -NotePropertyName 'non_nanite_coarse_pages' -NotePropertyValue ([int]$coarseValue.Matches[0].Groups[1].Value)}
$result | Add-Member -NotePropertyName 'screen_percentage' -NotePropertyValue $screenPercentage
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
