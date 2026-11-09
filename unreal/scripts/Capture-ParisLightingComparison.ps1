param([string]$EngineRoot='D:\Epic Games\UE_5.8',[string]$OutputDirectory='docs\paris-lighting-comparison')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$saved=Join-Path (Split-Path $project) 'Saved'
$output=Join-Path $repo $OutputDirectory
New-Item -ItemType Directory -Force -Path $output | Out-Null
foreach($time in @('Day','Sunset','Night')){
    $log=Join-Path $saved ('paris-lighting-comparison-'+$time+'.log')
    $shot=Join-Path $saved 'Screenshots\paris-twin.png'
    $args=@(('"'+$project+'"'),'-game','-ParisTwin','-dx12','-sm6','-CustomConfig=ParisPhotoreal','-ParisPhotoreal','-ParisTwinPhotoCamera=Camera_Paris_Street','-ParisTwinWindowDetail',('-ParisTwinTime='+$time),'-ParisTwinQuality=1','-RenderOffscreen','-ResX=1280','-ResY=720','-NoSplash','-ExecCmds="r.ScreenPercentage 80"','-ParisTwinWaitForAssets','-ParisTwinCapture','-ParisTwinCaptureAfter=14','-ParisTwinBenchmark=17','-ParisTwinExit',('-abslog="'+$log+'"'))
    $started=Get-Date
    $process=Start-Process -WindowStyle Hidden -FilePath (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe') -ArgumentList $args -PassThru -Wait
    if($process.ExitCode -ne 0 -or -not(Test-Path -LiteralPath $shot) -or (Get-Item -LiteralPath $shot).LastWriteTime -lt $started -or -not(Select-String -LiteralPath $log -Pattern 'PARIS_TWIN_READY' -Quiet)){throw ('Screenshot failed: '+$time+'; inspect '+$log)}
    Copy-Item -LiteralPath $shot -Destination (Join-Path $output ($time+'.png'))
    Copy-Item -LiteralPath (Join-Path $saved 'paris-twin-performance.json') -Destination (Join-Path $output ($time+'-stats.json'))
    Write-Output ($time+' captured from Camera_Paris_Street')
}
