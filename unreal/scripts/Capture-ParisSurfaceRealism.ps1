param([string]$EngineRoot='D:\Epic Games\UE_5.8',[ValidateSet('Before','After')][string]$Stage='After',[ValidateSet('Day','Night','Rain')][string]$Time='Day',[ValidateSet('Street','Front','Windows')][string]$View='Street',[ValidatePattern('^[a-z0-9-]+$')][string]$OutputPrefix='paris-surface')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
if(@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'}).Count){throw 'Close AIWorld before capture'}
$saved=Join-Path (Split-Path $project) 'Saved'
$name=($OutputPrefix+'-'+$Stage+'-'+$View+'-'+$Time).ToLowerInvariant()
$log=Join-Path $saved ($name+'.log')
$camera=if($View -eq 'Windows'){'Street'}else{$View}
$args=@(('"'+$project+'"'),'-game','-ParisTwin','-dx12','-sm6','-CustomConfig=ParisPhotoreal','-ParisPhotoreal','-ParisTwinPhotoLook',('-ParisTwinPhotoCamera=Camera_Paris_'+$camera),'-ParisTwinQuality=2','-RenderOffscreen','-windowed','-ForceRes','-ResX=1280','-ResY=720','-unattended','-nosound','-NoSplash','-ExecCmds="r.ScreenPercentage 100,ShowHUD"','-ParisTwinNoPeople','-ParisTwinNoTraffic','-ParisTwinWaitForAssets','-ParisTwinCapture','-ParisTwinCaptureAfter=12','-ParisTwinBenchmark=17','-ParisTwinExit',('-abslog="'+$log+'"'))
if($View -eq 'Street'){$args+='-ParisTwinTerraceView=0'}
if($View -eq 'Windows'){$args+='-ParisTwinWindowDetail'}
$args+=('-ParisTwinTime='+$(if($Time -eq 'Night'){'Night'}else{'Day'}))
if($Time -eq 'Rain'){$args+='-ParisTwinRain'}
$started=Get-Date
$p=Start-Process -WindowStyle Hidden -FilePath (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe') -ArgumentList $args -PassThru -Wait
if($p.ExitCode -ne 0 -or (Select-String -LiteralPath $log -Pattern 'Fatal error|Failed to compile Material|LogMaterial: Error|LogShaderCompilers: Error|PARIS_REFERENCE_INVALID|PARIS_REFERENCE_MISSING' -Quiet)){throw ('Capture failed '+$name)}
$shot=Join-Path $saved 'Screenshots\paris-twin.png'
if(-not(Test-Path -LiteralPath $shot) -or (Get-Item -LiteralPath $shot).LastWriteTime -lt $started){throw 'No fresh screenshot'}
Copy-Item -LiteralPath $shot -Destination (Join-Path $repo ('docs\'+$name+'.png'))
Copy-Item -LiteralPath (Join-Path $saved 'paris-twin-performance.json') -Destination (Join-Path $repo ('docs\'+$name+'-performance.json'))
Get-Content -LiteralPath (Join-Path $saved 'paris-twin-performance.json') -Raw -Encoding UTF8 | ConvertFrom-Json | Select-Object fps,seine_look,reference_models,active_photo_camera,camera_pitch_degrees | ConvertTo-Json -Depth 4
