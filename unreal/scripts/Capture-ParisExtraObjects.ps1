param([string]$EngineRoot='D:\Epic Games\UE_5.8',[ValidateSet('After','Before','Cafe','Night')][string]$View='After',[ValidateRange(0,5)][int]$Spot=3)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$active=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'})
if($active.Count){throw 'Close AIWorld before capture'}
$name='paris-extra-objects-'+$View.ToLower();$saved=Join-Path (Split-Path $project) 'Saved';$log=Join-Path $saved ($name+'.log')
$args=@(('"'+$project+'"'),'-game','-ParisTwin','-dx12','-sm6','-CustomConfig=ParisPhotoreal','-ParisPhotoreal','-ParisTwinPhotoCamera=Camera_Paris_Street','-ParisTwinQuality=1','-ParisTwinFestival','-RenderOffscreen','-windowed','-ForceRes','-ResX=1280','-ResY=720','-unattended','-nosound','-NoSplash','-ExecCmds="r.ScreenPercentage 80"','-ParisTwinWaitForAssets','-ParisTwinCapture','-ParisTwinCaptureAfter=9','-ParisTwinBenchmark=15','-ParisTwinExit',('-abslog="'+$log+'"'))
if($View -eq 'Cafe'){$args+=@('-ParisTwinLuxuryView','-ParisTwinLuxuryClose')}else{$args+='-ParisTwinExtraObjectsView'}
if($View -eq 'Before'){$args+='-ParisTwinNoExtraObjects'}
if($View -eq 'Night'){$args+=@('-ParisTwinTime=Night','-ParisTwinRain')}
$started=Get-Date
$p=Start-Process -WindowStyle Hidden -FilePath (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe') -ArgumentList $args -PassThru -Wait
if($p.ExitCode -ne 0 -or (Select-String -LiteralPath $log -Pattern 'Fatal error|Failed to compile Material|LogMaterial: Error|LogShaderCompilers: Error' -Quiet)){throw ('Capture failed: '+$name)}
$shot=Join-Path $saved 'Screenshots\paris-twin.png'
if(-not(Test-Path -LiteralPath $shot) -or (Get-Item -LiteralPath $shot).LastWriteTime -lt $started){throw 'No fresh screenshot'}
Copy-Item -LiteralPath $shot -Destination (Join-Path $repo ('docs\'+$name+'.png'))
Copy-Item -LiteralPath (Join-Path $saved 'paris-twin-performance.json') -Destination (Join-Path $repo ('docs\'+$name+'-performance.json'))
Get-Content -LiteralPath (Join-Path $saved 'paris-twin-performance.json') -Raw -Encoding UTF8 | ConvertFrom-Json | Select-Object fps,luxury_models,street_shop_displays,street_terrace_parasols,street_extra_objects,street_extra_visible_parts,minimap_ready | ConvertTo-Json
