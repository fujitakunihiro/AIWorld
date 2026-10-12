param([string]$EngineRoot='D:\Epic Games\UE_5.8', [switch]$Editor, [switch]$SkipServer)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$binary=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
if(-not (Test-Path -LiteralPath $binary)){throw "Unreal Engine not found: $EngineRoot"}
if(-not (Test-Path -LiteralPath (Join-Path $repo 'unreal\AIWorld\Binaries\Win64\UnrealEditor-AIWorld.dll'))){
    & (Join-Path $PSScriptRoot 'Build-AIWorldUE.ps1') -EngineRoot $EngineRoot
}
if(-not $SkipServer){
    Push-Location -LiteralPath $repo
    try{& docker compose -f compose.yaml -f compose.unreal.yaml up --build -d backend;if($LASTEXITCODE -ne 0){throw 'Simulation startup failed'}}finally{Pop-Location}
    $ready=$false
    for($i=0;$i -lt 30;$i++){try{$r=Invoke-RestMethod 'http://127.0.0.1:3001/api/health' -TimeoutSec 2;if($r.ok){$ready=$true;break}}catch{};Start-Sleep -Seconds 1}
    if(-not $ready){throw 'Simulation did not become healthy'}
}
# A visible game/editor window is the result explicitly requested by the player.
$launchArgs=@('"'+$project+'"','-NoSplash','-dx11')
if(-not $Editor){$launchArgs+=@('-game','-windowed','-ResX=1440','-ResY=900')}
Start-Process -FilePath $binary -ArgumentList $launchArgs
