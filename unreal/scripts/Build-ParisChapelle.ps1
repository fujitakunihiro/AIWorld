param([string]$EngineRoot='D:\Epic Games\UE_5.8')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$running=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'})
if($running.Count){throw 'Close the AIWorld preview/editor before creating chapel assets'}
$base=Join-Path $repo 'unreal\assets\sainte-chapelle';$manifest=Get-Content -Raw -LiteralPath (Join-Path $base 'manifest.json') | ConvertFrom-Json
$raw=Join-Path $base 'Raw\stained-glass.jpg';New-Item -ItemType Directory -Path (Split-Path $raw) -Force | Out-Null
if(-not(Test-Path -LiteralPath $raw)){
    $temp=$raw+'.part'
    try{& curl.exe -L --fail --silent --show-error -A 'AIWorld-Paris/1.0' -o $temp $manifest.download_url;if($LASTEXITCODE -ne 0){throw 'CC0 photo download failed'};if((Get-FileHash -LiteralPath $temp -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.sha256){throw 'Photo hash differs'};Move-Item -LiteralPath $temp -Destination $raw -Force}finally{if(Test-Path -LiteralPath $temp){Remove-Item -LiteralPath $temp}}
}
if((Get-FileHash -LiteralPath $raw -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.sha256){throw 'Photo hash differs'}
New-Item -ItemType Directory -Path (Join-Path $repo 'unreal\AIWorld\Content\ParisPhotoreal\SainteChapelle') -Force | Out-Null
$editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe';$log=Join-Path (Split-Path $project) 'Saved\paris-chapelle-bake.log'
& $editor $project '-run=pythonscript' ('-script='+(Join-Path $PSScriptRoot 'bake-paris-chapelle.py')) '-unattended' '-nullrhi' '-nosplash' '-stdout' '-UTF8Output' "-abslog=$log"
if($LASTEXITCODE -ne 0 -or -not(Select-String -LiteralPath $log -Pattern 'PARIS_CHAPELLE_MATERIAL_READY' -Quiet)){throw 'Chapel material build failed'}
