param([string]$EngineRoot='D:\Epic Games\UE_5.8')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$running=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'})
if($running.Count){throw 'Close the AIWorld preview/editor before rebuilding weathering assets'}
$backup=Join-Path $repo ('backups\paris-weathering-assets-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backup -Force | Out-Null
foreach($name in @('M_ParisRoadAsphalt','M_ParisLimestone','M_ParisCathedralStone','M_ParisWeatheringStreak','M_ParisWeatheringBase')){
    $file=Join-Path $repo ('unreal\AIWorld\Content\Materials\'+$name+'.uasset')
    if(Test-Path -LiteralPath $file){Copy-Item -LiteralPath $file -Destination $backup}
}
$python=Join-Path $repo 'gis\.venv\Scripts\python.exe'
$facade=Join-Path (Split-Path $project) 'Content\Data\paris-photo-frontages-source.json'
if(-not(Test-Path -LiteralPath $facade)){& $python (Join-Path $PSScriptRoot 'generate_paris_frontages.py');if($LASTEXITCODE -ne 0){throw 'Facade source generation failed'}}
& $python (Join-Path $PSScriptRoot 'generate_paris_weathering.py')
if($LASTEXITCODE -ne 0){throw 'Weathering geometry generation failed'}
$log=Join-Path (Split-Path $project) 'Saved\paris-weathering-bake.log'
& (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe') $project '-run=pythonscript' ('-script='+(Join-Path $PSScriptRoot 'bake-paris-weathering.py')) -CustomConfig=ParisPhotoreal -unattended -nullrhi -nosound -nosplash -stdout -UTF8Output ('-abslog='+$log)
if($LASTEXITCODE -ne 0 -or -not(Select-String -LiteralPath $log -Pattern 'PARIS_WEATHERING_ASSETS_READY' -Quiet) -or (Select-String -LiteralPath $log -Pattern 'Failed to compile Material|LogMaterial: Error|LogPython: Error' -Quiet)){throw 'Weathering bake failed; inspect Saved/paris-weathering-bake.log'}
