param([string]$EngineRoot='D:\Epic Games\UE_5.8',[string]$ReportPath='')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$saved=Join-Path (Split-Path $project) 'Saved'
$editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$raw=Join-Path $saved 'paris-twin-performance.json'
$log=Join-Path $saved 'paris-navigation-long-run.log'
if(-not $ReportPath){$ReportPath=Join-Path $repo 'docs\paris-twin-phase7-navigation-long-run.json'}
# t.OverrideFPS sets FApp's simulation delta in the installed engine's
# UnrealEngine.cpp. Run without a renderer and never interpret this run's
# synthetic FPS as rendering performance. Each 0.1s frame is two AI steps.
$arguments=@('"'+$project+'"','-game','-ParisTwin','-nullrhi','-unattended','-nosound','-nosplash',
    '-ParisTwinBenchmark=10','-ParisTwinExit','-ExecCmds="t.OverrideFPS 10,t.MaxFPS 0,r.VSync 0,t.IdleWhenNotForeground 0"',('-abslog="'+$log+'"'))
$started=Get-Date
$process=Start-Process -FilePath $editor -ArgumentList $arguments -WindowStyle Hidden -PassThru
if(-not $process.WaitForExit(90000)){if(-not $process.HasExited){Stop-Process -Id $process.Id};throw 'Owned long-run helper exceeded its 90s wall-time limit'}
if($process.ExitCode -ne 0 -or -not(Test-Path -LiteralPath $raw) -or (Get-Item -LiteralPath $raw).LastWriteTime -lt $started){throw 'Long-run simulation did not produce a fresh result'}
if(Select-String -LiteralPath $log -Pattern 'Fatal error|Assertion failed' -Quiet){throw 'Long-run simulation reported a native error'}
$result=Get-Content -LiteralPath $raw -Raw | ConvertFrom-Json
if([Math]::Abs($result.fps-10) -gt .001 -or [Math]::Abs($result.frame_p95_ms-100) -gt .01){throw 'The fixed 0.1s simulation delta was not applied; step count cannot be inferred'}
$output=[ordered]@{
    kind='fixed_delta_nullrhi_simulation_qa';not_render_performance=$true;engine='UE 5.8.3 Development Editor -game';
    fixed_frame_seconds=0.1;fixed_delta_verified=$true;ai_step_seconds=0.05;measured_phase_frames=$result.frames;
    minimum_ai_steps=([int]$result.frames*2);minimum_simulated_seconds=([int]$result.frames*0.1);
    people=$result.pedestrians_total;navigation_nodes=$result.navigation_nodes;navigation_edges=$result.navigation_edges;
    cross_source_visits_started=$result.network_visits;cross_source_visits_completed=$result.network_visits_completed;
    all_visits_completed=$result.visits_completed;cancelled_returns_completed=$result.visits_aborted;
    distance_travelled_m=$result.pedestrian_distance_travelled_m;wall_time_seconds=((Get-Date)-$started).TotalSeconds;
    scene_sha256=((Get-FileHash -LiteralPath (Join-Path (Split-Path $project) 'Content\Data\paris-digital-twin.json') -Algorithm SHA256).Hash.ToLowerInvariant());
    run_utc=$started.ToUniversalTime().ToString('o')
}
$output | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReportPath -Encoding utf8
if($output.minimum_ai_steps -lt 5000 -or $output.cross_source_visits_completed -le 0 -or $output.people -ne 160){throw 'Long-run result did not cover 5000 steps, the full population and a completed cross-source round trip'}
Write-Output "Long-run passed: at least $($output.minimum_ai_steps) AI steps; $($output.cross_source_visits_completed) cross-source round trips completed. Not a rendering benchmark."
