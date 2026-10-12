param([string]$EngineRoot='D:\Epic Games\UE_5.8', [switch]$SkipAssets, [switch]$Game)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$build=Join-Path $EngineRoot 'Engine\Build\BatchFiles\Build.bat'
if(-not (Test-Path -LiteralPath $build)){throw "Unreal Engine not found: $EngineRoot"}
& (Join-Path $PSScriptRoot 'Prepare-UEBuild.ps1')
Push-Location -LiteralPath $repo
try {
    if(-not(Get-Command node -ErrorAction SilentlyContinue)){throw 'Node.js 22 or newer is required to export the authored models'}
    if(-not(Test-Path -LiteralPath 'node_modules\tsx')){& npm.cmd ci;if($LASTEXITCODE -ne 0){throw 'Dependency install failed'}}
    & node --import tsx tools/export-unreal.ts
    if($LASTEXITCODE -ne 0){throw 'Model export failed'}
    $target=if($Game){'AIWorld'}else{'AIWorldEditor'}
    & $build $target Win64 Development $project -WaitMutex -NoHotReloadFromIDE -NoUBA -MaxParallelActions=1
    if($LASTEXITCODE -ne 0){throw 'Unreal compilation failed'}
    if(-not $SkipAssets){
        $editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
        $assets=Join-Path $repo 'unreal\scripts\create-assets.py'
        & $editor $project '-run=pythonscript' "-script=$assets" -unattended -nullrhi -nosplash -stdout -UTF8Output
        if($LASTEXITCODE -ne 0){throw 'Unreal asset generation failed'}
    }
} finally {Pop-Location}
