param([string]$EngineRoot='D:\Epic Games\UE_5.8',[switch]$Offline)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$running=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'})
if($running.Count){throw 'Close the AIWorld preview/editor before importing sound assets'}
$python=Join-Path $repo 'gis\.venv\Scripts\python.exe'
$pipOptions=@();if($Offline){$pipOptions+='--no-index'}
& $python -m pip install --disable-pip-version-check @pipOptions -r (Join-Path $PSScriptRoot 'requirements-audio.lock')
if($LASTEXITCODE -ne 0){throw 'Pinned offline-audio tools install failed'}
$audioOptions=@();if($Offline){$audioOptions+='--offline'}
& $python (Join-Path $PSScriptRoot 'generate_paris_soundscape.py') @audioOptions
if($LASTEXITCODE -ne 0){throw 'Verified soundscape generation failed'}
$log=Join-Path (Split-Path $project) 'Saved\paris-soundscape-bake.log'
& (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe') $project -run=pythonscript ('-script='+(Join-Path $PSScriptRoot 'bake-paris-soundscape.py')) -unattended -nullrhi -nosound -nosplash -stdout -UTF8Output ('-abslog='+$log)
if($LASTEXITCODE -ne 0 -or -not(Select-String -LiteralPath $log -Pattern 'PARIS_SOUNDSCAPE_ASSETS_READY' -Quiet)){throw 'Sound import failed; inspect Saved/paris-soundscape-bake.log'}
