param([string]$EngineRoot='D:\Epic Games\UE_5.8',[ValidateRange(1,3)][int]$View=1,[ValidateSet('Day','Sunset','Night')][string]$Time='Day')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
if(@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'}).Count){throw 'Close AIWorld before capture'}
$saved=Join-Path (Split-Path $project) 'Saved';$name='paris-notredame-interior-'+$View;$log=Join-Path $saved ($name+'.log')
$args=@(('"'+$project+'"'),'-game','-ParisTwin','-dx12','-sm6','-CustomConfig=ParisPhotoreal','-ParisPhotoreal',('-ParisTwinNotreDameInterior='+$View),'-ParisTwinPhotoCamera=Camera_Paris_Street','-ParisTwinQuality=2','-RenderOffscreen','-windowed','-ForceRes','-ResX=1280','-ResY=720','-unattended','-nosound','-NoSplash','-ExecCmds="r.ScreenPercentage 100,ShowHUD"','-ParisTwinNoPeople','-ParisTwinNoTraffic','-ParisTwinWaitForAssets','-ParisTwinCapture','-ParisTwinCaptureAfter=10','-ParisTwinBenchmark=10','-ParisTwinExit',('-ParisTwinTime='+$Time),('-abslog="'+$log+'"'))
$started=Get-Date
$p=Start-Process -WindowStyle Hidden -FilePath (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe') -ArgumentList $args -PassThru -Wait
if($p.ExitCode -ne 0 -or (Select-String -LiteralPath $log -Pattern 'Fatal error|Failed to compile Material|LogMaterial: Error|LogShaderCompilers: Error|PARIS_NOTREDAME_INTERIOR_MATERIALS_MISSING' -Quiet)){throw ('Capture failed '+$name)}
$shot=Join-Path $saved 'Screenshots\paris-twin.png'
if(-not(Test-Path -LiteralPath $shot) -or (Get-Item -LiteralPath $shot).LastWriteTime -lt $started){throw 'No fresh screenshot'}
Copy-Item -LiteralPath $shot -Destination (Join-Path $repo ('docs\'+$name+'.png'))
Copy-Item -LiteralPath (Join-Path $saved 'paris-twin-performance.json') -Destination (Join-Path $repo ('docs\'+$name+'-performance.json'))
Select-String -LiteralPath $log -Pattern 'PARIS_NOTREDAME_INTERIOR_READY' | Select-Object -First 1 | ForEach-Object {$_.Line}
Get-Content -LiteralPath (Join-Path $saved 'paris-twin-performance.json') -Raw -Encoding UTF8 | ConvertFrom-Json | Select-Object fps | ConvertTo-Json
