param([string]$EngineRoot='D:\Epic Games\UE_5.8',[ValidateSet('Before','After','Sunset','Night')][string]$View='After',[ValidatePattern('^[a-z0-9-]+$')][string]$OutputPrefix='paris-luxury',[switch]$Festival,[switch]$Close,[switch]$District,[ValidateRange(0,5)][int]$Spot=0)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$running=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'})
if($running.Count){throw 'Close the AIWorld preview/editor before capturing a comparison'}
$log=Join-Path (Split-Path $project) ('Saved\'+$OutputPrefix+'-'+$View.ToLower()+'.log')
$arguments=@(('"'+$project+'"'),'-game','-ParisTwin','-dx12','-sm6','-CustomConfig=ParisPhotoreal','-ParisPhotoreal','-ParisTwinLuxuryView','-ParisTwinPhotoCamera=Camera_Paris_Street','-ParisTwinQuality=1','-windowed','-ForceRes','-ResX=1280','-ResY=720','-RenderOffscreen','-unattended','-nosound','-NoSplash','-ParisTwinCapture','-ParisTwinWaitForAssets','-ParisTwinCaptureAfter=12','-ParisTwinBenchmark=18','-ParisTwinExit','-ExecCmds="r.ScreenPercentage 80,ShowHUD"',('-abslog="'+$log+'"'))
if($View -eq 'Before'){$arguments+='-ParisTwinNoLuxury'}
if($Festival){$arguments+='-ParisTwinFestival'}
if($Close){$arguments+='-ParisTwinLuxuryClose'}
if($District){$arguments+=@('-ParisTwinDistrictView',('-ParisTwinDistrictSpot='+$Spot))}
if($View -eq 'Night'){$arguments+=@('-ParisTwinTime=Night','-ParisTwinRain')}
if($View -eq 'Sunset'){$arguments+='-ParisTwinTime=Sunset'}
$started=Get-Date
$p=Start-Process -WindowStyle Hidden -FilePath (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe') -ArgumentList $arguments -PassThru
$p.WaitForExit();if($p.ExitCode -ne 0){throw ('Luxury capture failed: '+$p.ExitCode)}
if(Select-String -LiteralPath $log -Pattern 'Failed to compile Material|LogMaterial: Error|LogShaderCompilers: Error' -Quiet){throw 'Capture contains a material compilation error; inspect Saved/paris-luxury-*.log'}
$image=Join-Path (Split-Path $project) 'Saved\Screenshots\paris-twin.png'
if(-not(Test-Path -LiteralPath $image) -or (Get-Item -LiteralPath $image).LastWriteTime -lt $started){throw 'Luxury capture did not produce a fresh screenshot'}
$name=$OutputPrefix+'-'+$View.ToLower()
Copy-Item -LiteralPath $image -Destination (Join-Path $repo ('docs\'+$name+'.png'))
Copy-Item -LiteralPath (Join-Path (Split-Path $project) 'Saved\paris-twin-performance.json') -Destination (Join-Path $repo ('docs\'+$name+'-performance.json'))
$report=Get-Content -LiteralPath (Join-Path $repo ('docs\'+$name+'-performance.json')) -Raw | ConvertFrom-Json
$report | Select-Object fps,frame_p95_ms,luxury_models,luxury_instances,luxury_urns,luxury_tables,luxury_canopies,luxury_hanging_baskets,luxury_light_strings,luxury_bulbs,luxury_upper_windows,luxury_facade_banners,luxury_facade_lanterns,luxury_street_garlands,luxury_street_flags,luxury_street_bulbs,luxury_lit_windows | Format-List
