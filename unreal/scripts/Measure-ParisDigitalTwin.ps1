param(
    [string]$EngineRoot='D:\Epic Games\UE_5.8',
    [ValidateSet('Overview','Street','NotreDame','WalkFirst','WalkThird','Traffic','Cafe')][string]$View='Overview',
    [ValidateSet('Low','Medium','High')][string]$Quality='Medium',
    [ValidateRange(10,120)][int]$Duration=20,
    [string]$ReportPath='',
    [switch]$LegacyJSON
)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$saved=Join-Path (Split-Path $project) 'Saved'
$editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$log=Join-Path $saved 'paris-twin-measure.log'
$performance=Join-Path $saved 'paris-twin-performance.json'
$shot=Join-Path $saved 'Screenshots\paris-twin.png'
$suffix=if($LegacyJSON){'-legacy'}else{''}
if(-not $ReportPath){$ReportPath=Join-Path $repo "docs\paris-twin-phase7-cafes-$($View.ToLower())$suffix-performance.json"}
$reportFolder=Split-Path $ReportPath
New-Item -ItemType Directory -Path $reportFolder -Force | Out-Null
$arguments=@('"'+$project+'"','-game','-ParisTwin','-dx11','-windowed','-ResX=1280','-ResY=720','-RenderOffscreen','-unattended','-nosound','-NoSplash',
    '-ParisTwinCapture',"-ParisTwinBenchmark=$Duration",'-ParisTwinExit','-ExecCmds="t.MaxFPS 0,r.VSync 0"',
    ('-ParisTwinQuality='+@{Low=0;Medium=1;High=2}[$Quality]),('-abslog="'+$log+'"'))
if($LegacyJSON){$arguments+='-ParisTwinLegacyJSON'}
if($View -eq 'Cafe'){$arguments+='-ParisTwinCafeView'}
if($View -eq 'Traffic'){$arguments+='-ParisTwinTrafficView'}
if($View -eq 'Street'){$arguments+='-ParisTwinEye'}
if($View -eq 'WalkFirst'){$arguments+='-ParisTwinWalk'}
if($View -eq 'WalkThird'){$arguments+='-ParisTwinThirdPerson'}
if($View -eq 'NotreDame'){$arguments+='-ParisTwinLandmark=1'}
$started=Get-Date
$process=Start-Process -FilePath $editor -ArgumentList $arguments -WindowStyle Hidden -PassThru
if(-not $process.WaitForExit(240000)){
    if(-not $process.HasExited){Stop-Process -Id $process.Id}
    throw 'Paris benchmark did not finish within four minutes; its owned helper process was stopped'
}
if($process.ExitCode -ne 0 -or -not(Test-Path -LiteralPath $performance) -or (Get-Item -LiteralPath $performance).LastWriteTime -lt $started){throw 'Paris benchmark failed or did not produce a fresh report'}
if(Select-String -LiteralPath $log -Pattern 'Fatal error|Assertion failed|missing usage flag InstancedStaticMeshes|CPU data not available on selected LOD' -Quiet){throw 'Unreal reported a benchmark mesh/material error'}
$result=Get-Content -LiteralPath $performance -Raw | ConvertFrom-Json
if($View -in @('Traffic','Cafe') -and -not $result.camera_eye){throw 'Traffic inspection did not find an unobstructed eye-level camera'}
if($View -in @('WalkFirst','WalkThird') -and -not $result.walking){throw 'Requested walking view did not become active'}
$result | Add-Member -NotePropertyName 'render_offscreen' -NotePropertyValue $true
$result | Add-Member -NotePropertyName 'duration_seconds' -NotePropertyValue $Duration
$result | Add-Member -NotePropertyName 'warmup_seconds' -NotePropertyValue 5
$result | Add-Member -NotePropertyName 'run_utc' -NotePropertyValue $started.ToUniversalTime().ToString('o')
$result | Add-Member -NotePropertyName 'engine' -NotePropertyValue 'UE 5.8.3 Development Editor -game'
$result | Add-Member -NotePropertyName 'gpu' -NotePropertyValue ((Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join ', ')
$scene=Join-Path (Split-Path $project) 'Content\Data\paris-digital-twin.json'
$result | Add-Member -NotePropertyName 'scene_sha256' -NotePropertyValue ((Get-FileHash -LiteralPath $scene -Algorithm SHA256).Hash.ToLowerInvariant())
$result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $ReportPath -Encoding utf8
if(Test-Path -LiteralPath $shot){
    if((Get-Item -LiteralPath $shot).LastWriteTime -ge $started){
        $screenshots=Join-Path $reportFolder 'screenshots';New-Item -ItemType Directory -Path $screenshots -Force | Out-Null
        Copy-Item -LiteralPath $shot -Destination (Join-Path $screenshots "paris-twin-phase7-cafes-$($View.ToLower())$suffix.png")
    }
}
Write-Output "Saved $View / $Quality benchmark: $ReportPath"
Write-Output "FPS $($result.fps) | P95 $($result.frame_p95_ms)ms"
