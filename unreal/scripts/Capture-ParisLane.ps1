param([string]$EngineRoot='D:\Epic Games\UE_5.8',[ValidateSet('After','Before','Night','Rain')][string]$View='After')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
if(@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'}).Count){throw 'Close AIWorld before lane capture'}
$saved=Join-Path (Split-Path $project) 'Saved';$name='paris-lane-'+$View.ToLower();$log=Join-Path $saved ($name+'.log')
$args=@(('"'+$project+'"'),'-game','-ParisTwin','-dx12','-sm6','-CustomConfig=ParisPhotoreal','-ParisPhotoreal','-ParisTwinLane','-ParisTwinPhotoCamera=Camera_Paris_Street','-ParisTwinQuality=2','-RenderOffscreen','-windowed','-ForceRes','-ResX=1280','-ResY=720','-unattended','-nosound','-NoSplash','-ExecCmds="r.ScreenPercentage 100,ShowHUD"','-ParisTwinNoPeople','-ParisTwinNoTraffic','-ParisTwinWaitForAssets','-ParisTwinCapture','-ParisTwinCaptureAfter=10','-ParisTwinBenchmark=15','-ParisTwinExit',('-abslog="'+$log+'"'))
if($View -eq 'Before'){$args+='-ParisTwinLaneBaseline'}
if($View -eq 'Night'){$args+='-ParisTwinTime=Night'}
if($View -eq 'Rain'){$args+='-ParisTwinRain'}
$started=Get-Date
$p=Start-Process -WindowStyle Hidden -FilePath (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe') -ArgumentList $args -PassThru -Wait
if($p.ExitCode -ne 0 -or (Select-String -LiteralPath $log -Pattern 'Fatal error|Failed to compile Material|LogMaterial: Error|LogShaderCompilers: Error|PARIS_REFERENCE_INVALID|PARIS_REFERENCE_MISSING' -Quiet)){throw ('Lane capture failed '+$name)}
$shot=Join-Path $saved 'Screenshots\paris-twin.png'
if(-not(Test-Path -LiteralPath $shot) -or (Get-Item -LiteralPath $shot).LastWriteTime -lt $started){throw 'No fresh lane screenshot'}
Copy-Item -LiteralPath $shot -Destination (Join-Path $repo ('docs\'+$name+'.png'))
Copy-Item -LiteralPath (Join-Path $saved 'paris-twin-performance.json') -Destination (Join-Path $repo ('docs\'+$name+'-performance.json'))
Get-Content -LiteralPath (Join-Path $saved 'paris-twin-performance.json') -Raw -Encoding UTF8 | ConvertFrom-Json | Select-Object fps,lane_look,lane_baseline,reference_models,lane | ConvertTo-Json -Depth 4
