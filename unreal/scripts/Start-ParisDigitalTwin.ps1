param([string]$EngineRoot='D:\Epic Games\UE_5.8',[switch]$Download,[switch]$Refresh,[switch]$Build,[switch]$Eye,[switch]$Capture,[ValidateRange(0,120)][double]$Benchmark=0,[switch]$ExitAfterBenchmark,[switch]$NoShadows)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python=Join-Path $repo 'gis\.venv\Scripts\python.exe'
if(-not(Test-Path -LiteralPath $python)){& py -3.12 -m venv (Join-Path $repo 'gis\.venv');if($LASTEXITCODE -ne 0){throw 'Python 3.12 environment creation failed'}}
Push-Location -LiteralPath $repo
$previousPythonPath=$env:PYTHONPATH
$previousEncoding=$env:PYTHONIOENCODING
try {
    $env:PYTHONPATH=Join-Path $repo 'gis'
    $env:PYTHONIOENCODING='utf-8'
    & $python -m pip install --disable-pip-version-check -r gis/requirements.lock
    if($LASTEXITCODE -ne 0){throw 'Pinned GIS dependency install failed'}
    if($Download){$options=@('download');if($Refresh){$options+='--refresh'};& $python -m paris_twin @options;if($LASTEXITCODE -ne 0){throw 'GIS download failed'}}
    & $python -m paris_twin generate --offline
    if($LASTEXITCODE -ne 0){throw 'Offline GIS generation failed; acquire raw data with -Download first'}
    & $python -m paris_twin validate --offline
    if($LASTEXITCODE -ne 0){throw 'GIS validation failed'}
}finally{$env:PYTHONPATH=$previousPythonPath;$env:PYTHONIOENCODING=$previousEncoding;Pop-Location}
$dll=Join-Path $repo 'unreal\AIWorld\Binaries\Win64\UnrealEditor-AIWorld.dll'
$newestSource=Get-ChildItem -LiteralPath (Join-Path $repo 'unreal\AIWorld\Source') -File -Recurse | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if($Build -or -not(Test-Path -LiteralPath $dll) -or $newestSource.LastWriteTime -gt (Get-Item -LiteralPath $dll).LastWriteTime){& (Join-Path $PSScriptRoot 'Build-AIWorldUE.ps1') -EngineRoot $EngineRoot;if($LASTEXITCODE -ne 0){throw 'Native build failed'}}
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
if(-not(Test-Path -LiteralPath $editor)){throw 'Unreal Engine is not installed at '+$EngineRoot}
$launchArgs=@('"'+$project+'"','-game','-ParisTwin','-dx11','-windowed','-ResX=1280','-ResY=720','-NoSplash')
if($Eye){$launchArgs+='-ParisTwinEye'}
if($Capture){$launchArgs+='-ParisTwinCapture'}
if($NoShadows){$launchArgs+='-ParisTwinNoShadows'}
if($Benchmark -gt 0){$launchArgs+="-ParisTwinBenchmark=$Benchmark"}
if($ExitAfterBenchmark){$launchArgs+='-ParisTwinExit'}
Start-Process -FilePath $editor -ArgumentList $launchArgs
