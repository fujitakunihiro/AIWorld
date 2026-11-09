param([string]$EngineRoot='D:\Epic Games\UE_5.8',[switch]$SkipGeometry)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
if(@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'}).Count){throw 'Close AIWorld before florist tests'}
if(-not $SkipGeometry){& (Join-Path $repo 'gis\.venv\Scripts\python.exe') -m unittest discover -s (Join-Path $PSScriptRoot 'tests') -p test_paris_florist.py -v;if($LASTEXITCODE -ne 0){throw 'Florist mesh validation failed'}}
$passes=@()
foreach($mode in @('detailed','fallback')){
    $log=Join-Path (Split-Path $project) ('Saved\paris-florist-'+$mode+'-tests.log')
    $engineArgs=@($project,'-game','-ParisTwin','-ParisPhotoreal','-CustomConfig=ParisPhotoreal','-unattended','-nullrhi','-nosound','-nosplash','-ExecCmds=Automation RunTests ParisDigitalTwin.Live.BusinessesAndTerraces','-TestExit=Automation Test Queue Empty',('-abslog='+$log),'-stdout')
    if($mode -eq 'fallback'){$engineArgs+='-ParisTwinSimpleFlorists'}
    & (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe') @engineArgs | Out-Null
    if($LASTEXITCODE -ne 0 -or -not(Select-String -LiteralPath $log -Pattern 'Result=\{Success\}.*Name=\{BusinessesAndTerraces\}' -Quiet)){throw ('Florist runtime validation failed: '+$mode)}
    $passes+=$mode
    Write-Output ('Florist runtime passed: '+$mode)
}
@{runtime_passes=$passes;checks=@('all shared parts load at mapped shops','no new walking collisions','same source placement for all parts','F6 hides detailed parts','explicit legacy fallback');reference_sha256='236bc83c6a46e1a773630d8cfe86adf979d9f0119923238d59781afe56a11dea'} | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $repo 'docs\paris-florist-validation.json') -Encoding utf8
