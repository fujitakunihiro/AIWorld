param([string]$EngineRoot='D:\Epic Games\UE_5.8',[ValidateSet('After','Before')][string]$View='After')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
if(@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'}).Count){throw 'Close AIWorld before florist capture'}
$saved=Join-Path (Split-Path $project) 'Saved';$name='paris-florist-'+$View.ToLower();$log=Join-Path $saved ($name+'.log')
$launch=@(('"'+$project+'"'),'-game','-ParisTwin','-dx12','-sm6','-CustomConfig=ParisPhotoreal','-ParisPhotoreal','-ParisTwinShopView=florist','-ParisTwinQuality=2','-RenderOffscreen','-windowed','-ForceRes','-ResX=1280','-ResY=720','-unattended','-nosound','-NoSplash','-ExecCmds="r.ScreenPercentage 100,ShowHUD,t.MaxFPS 0,r.VSync 0"','-ParisTwinNoPeople','-ParisTwinNoTraffic','-ParisTwinWaitForAssets','-ParisTwinCapture','-ParisTwinCaptureAfter=12','-ParisTwinBenchmark=18','-ParisTwinExit',('-abslog="'+$log+'"'))
if($View -eq 'Before'){$launch+='-ParisTwinSimpleFlorists'}
$launch+='-ParisTwinNoLuxury'
$started=Get-Date
$process=Start-Process -WindowStyle Hidden -FilePath (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe') -ArgumentList $launch -PassThru -Wait
if($process.ExitCode -ne 0 -or (Select-String -LiteralPath $log -Pattern 'Fatal error|Failed to compile Material|LogMaterial: Error|LogShaderCompilers: Error' -Quiet)){throw ('Florist capture failed '+$name)}
$shot=Join-Path $saved 'Screenshots\paris-twin.png'
if(-not(Test-Path -LiteralPath $shot) -or (Get-Item -LiteralPath $shot).LastWriteTime -lt $started){throw 'No fresh florist screenshot'}
if($View -eq 'After' -and -not(Select-String -LiteralPath $log -Pattern 'PARIS_FLORIST_READY shops=4 models=8' -Quiet)){throw 'Detailed florist meshes did not load'}
Copy-Item -LiteralPath $shot -Destination (Join-Path $repo ('docs\'+$name+'.png'))
Copy-Item -LiteralPath (Join-Path $saved 'paris-twin-performance.json') -Destination (Join-Path $repo ('docs\'+$name+'-performance.json'))
$result=Get-Content -LiteralPath (Join-Path $saved 'paris-twin-performance.json') -Raw -Encoding utf8 | ConvertFrom-Json
if(-not $result.camera_eye -or $result.selected_business_category -ne 'florist'){throw 'The inspection camera did not reach an unobstructed florist view'}
$result | Select-Object fps,frame_p95_ms,selected_business_category | ConvertTo-Json
