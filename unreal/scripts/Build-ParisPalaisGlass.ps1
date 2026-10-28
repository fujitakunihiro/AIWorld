param([string]$EngineRoot='D:\Epic Games\UE_5.8')
$ErrorActionPreference='Stop'
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$running=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'})
if($running.Count){throw 'Close the AIWorld preview/editor before creating Palais material'}
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
New-Item -ItemType Directory -Path (Join-Path $repo 'unreal\AIWorld\Content\ParisPhotoreal\Palais') -Force | Out-Null
$editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe';$log=Join-Path (Split-Path $project) 'Saved\palais-glass-bake.log'
& $editor $project '-run=pythonscript' ('-script='+(Join-Path $PSScriptRoot 'bake-paris-palais-glass.py')) '-unattended' '-nullrhi' '-nosplash' '-stdout' '-UTF8Output' "-abslog=$log"
if($LASTEXITCODE -ne 0 -or -not(Select-String -LiteralPath $log -Pattern 'PARIS_PALAIS_GLASS_READY' -Quiet)){throw 'Palais glass material build failed'}
