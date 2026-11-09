param([string]$EngineRoot='D:\Epic Games\UE_5.8',[ValidateSet('Street','Close','Before','Walk')][string]$View='Street')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$active=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'})
if($active.Count){throw 'Close AIWorld before capture'}
$name='paris-grime-map-'+$View.ToLower();$saved=Join-Path (Split-Path $project) 'Saved';$log=Join-Path $saved ($name+'.log')
$args=@(('"'+$project+'"'),'-game','-ParisTwin','-dx12','-sm6','-CustomConfig=ParisPhotoreal','-ParisPhotoreal','-ParisTwinPhotoCamera=Camera_Paris_Street','-ParisTwinTime=Day','-ParisTwinQuality=1','-ParisTwinFestival','-RenderOffscreen','-windowed','-ForceRes','-ResX=1280','-ResY=720','-unattended','-nosound','-NoSplash','-ExecCmds="r.ScreenPercentage 80"','-ParisTwinWaitForAssets','-ParisTwinCapture','-ParisTwinCaptureAfter=9','-ParisTwinBenchmark=15','-ParisTwinExit',('-abslog="'+$log+'"'))
if($View -in @('Close','Before')){$args+='-ParisTwinWeatheringView'}else{$args+=@('-ParisTwinDistrictView','-ParisTwinDistrictSpot=3')}
if($View -eq 'Before'){$args+='-ParisTwinNoWeathering'}
if($View -eq 'Walk'){$args=@($args | Where-Object {$_ -notmatch '^-Res[XY]='});$args+=@('-ParisTwinThirdPerson','-ResX=1600','-ResY=900')}
$started=Get-Date
$p=Start-Process -WindowStyle Hidden -FilePath (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe') -ArgumentList $args -PassThru -Wait
if($p.ExitCode -ne 0 -or (Select-String -LiteralPath $log -Pattern 'Fatal error|Failed to compile Material|LogMaterial: Error|LogShaderCompilers: Error' -Quiet)){throw ('Capture failed: '+$name)}
$shot=Join-Path $saved 'Screenshots\paris-twin.png'
if(-not(Test-Path -LiteralPath $shot) -or (Get-Item -LiteralPath $shot).LastWriteTime -lt $started){throw 'No fresh screenshot'}
Copy-Item -LiteralPath $shot -Destination (Join-Path $repo ('docs\'+$name+'.png'))
Copy-Item -LiteralPath (Join-Path $saved 'paris-twin-performance.json') -Destination (Join-Path $repo ('docs\'+$name+'-performance.json'))
$r=Get-Content -LiteralPath (Join-Path $saved 'paris-twin-performance.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$r | Select-Object fps,weathering_components,weathering_visible,minimap_ready,minimap_triangles,minimap_observer,walking,third_person | ConvertTo-Json
