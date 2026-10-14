param([string]$EngineRoot='D:\Epic Games\UE_5.8',[switch]$Download,[switch]$Refresh,[switch]$Build,[switch]$Eye,[switch]$Capture,[ValidateRange(0,120)][double]$Benchmark=0,[switch]$ExitAfterBenchmark,[switch]$NoShadows,[switch]$Footprints,[switch]$Issues,[string]$Config='',[switch]$DownloadBuildings,[ValidateRange(0,3)][int]$Landmark=0,[switch]$DownloadTerrain,[ValidateSet('Low','Medium','High')][string]$Quality='Medium',[switch]$NoStreetDetails,[switch]$Walk,[switch]$ThirdPerson,[switch]$NoPeople)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$gisOptions=@()
if($Config){$gisOptions=@('--config',(Resolve-Path -LiteralPath $Config).Path)}
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
    if($Download){$options=@('download');if($Refresh){$options+='--refresh'};& $python -m paris_twin @options @gisOptions;if($LASTEXITCODE -ne 0){throw 'GIS download failed'}}
    if($DownloadBuildings){$options=@('download-buildings');if($Refresh){$options+='--refresh'};& $python -m paris_twin @options @gisOptions;if($LASTEXITCODE -ne 0){throw 'IGN building acquisition failed'}}
    if($DownloadTerrain){$options=@('download-terrain');if($Refresh){$options+='--refresh'};& $python -m paris_twin @options @gisOptions;if($LASTEXITCODE -ne 0){throw 'IGN terrain acquisition failed'}}
    & $python -m paris_twin prepare --offline @gisOptions
    if($LASTEXITCODE -ne 0){throw 'Offline GIS generation failed; acquire raw data with -Download first'}
    & $python -m paris_twin validate --offline @gisOptions
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
if($Walk){$launchArgs+='-ParisTwinWalk'}
if($ThirdPerson){$launchArgs+='-ParisTwinThirdPerson'}
if($NoPeople){$launchArgs+='-ParisTwinNoPeople'}
if($Landmark -gt 0){$launchArgs+="-ParisTwinLandmark=$Landmark"}
if($Footprints){$launchArgs+='-ParisTwinFootprints'}
if($Issues){$launchArgs+='-ParisTwinIssues'}
if($Capture){$launchArgs+='-ParisTwinCapture'}
if($NoShadows){$launchArgs+='-ParisTwinNoShadows'}
$launchArgs+=('-ParisTwinQuality='+@{Low=0;Medium=1;High=2}[$Quality])
if($NoStreetDetails){$launchArgs+='-ParisTwinNoStreetDetails'}
if($Benchmark -gt 0){$launchArgs+="-ParisTwinBenchmark=$Benchmark"}
if($ExitAfterBenchmark){$launchArgs+='-ParisTwinExit'}
Start-Process -FilePath $editor -ArgumentList $launchArgs
