param([string]$EngineRoot='D:\Epic Games\UE_5.8',[switch]$NoncommercialStatue)
$ErrorActionPreference='Stop'
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$running=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'})
if($running.Count){throw 'Close the AIWorld Unreal preview/editor before replacing cathedral assets'}
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python=Join-Path $repo 'gis\.venv\Scripts\python.exe'
& $python (Join-Path $PSScriptRoot 'paris_photo_sources.py') --ensure
if($LASTEXITCODE -ne 0){throw 'Verified offline photographic surface cache is unavailable'}
& $python (Join-Path $PSScriptRoot 'generate_paris_architecture.py')
if($LASTEXITCODE -ne 0){throw 'Cathedral source generation failed'}
if($NoncommercialStatue){
    & $python (Join-Path $PSScriptRoot 'prepare_notredame_statue.py') --download
    if($LASTEXITCODE -ne 0){throw 'Licensed noncommercial sculpture preparation failed'}
}
$editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$script=Join-Path $PSScriptRoot 'bake-paris-cathedral-details.py'
& $editor $project '-run=pythonscript' "-script=$script" -CustomConfig=ParisPhotoreal -nullrhi -unattended -nosplash -stdout -UTF8Output
if($LASTEXITCODE -ne 0){throw 'Cathedral mesh/material generation failed'}
