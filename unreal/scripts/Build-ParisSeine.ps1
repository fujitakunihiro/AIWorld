param([string]$EngineRoot='D:\Epic Games\UE_5.8',[switch]$SkipGenerate)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
if(@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'}).Count){throw 'Close AIWorld before building Seine assets'}
if(-not $SkipGenerate){& (Join-Path $repo 'gis\.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'generate_paris_seine.py');if($LASTEXITCODE -ne 0){throw 'Seine generation failed'}}
$log=Join-Path (Split-Path $project) 'Saved\paris-seine-bake.log'
& (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe') $project -run=pythonscript ('-script='+(Join-Path $PSScriptRoot 'bake-paris-seine.py')) -CustomConfig=ParisPhotoreal -unattended -nullrhi -nosound -nosplash -stdout -UTF8Output ('-abslog='+$log)
if($LASTEXITCODE -ne 0 -or -not(Select-String -LiteralPath $log -Pattern 'PARIS_SEINE_ASSETS_READY' -Quiet)){throw 'Seine bake failed'}
