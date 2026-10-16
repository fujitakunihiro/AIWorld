param([string]$EngineRoot='D:\Epic Games\UE_5.8',[switch]$ImportCandidate,[switch]$SkipScannedFacade)
$ErrorActionPreference='Stop'
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$running=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'})
if($running.Count){throw 'Close the AIWorld Unreal preview/editor before generating assets; open packages cannot be replaced safely'}
$editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
New-Item -ItemType Directory -Path (Join-Path (Split-Path $project) 'Content\ParisPhotoreal\Generated') -Force | Out-Null
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python=Join-Path $repo 'gis\.venv\Scripts\python.exe'
& $python (Join-Path $PSScriptRoot 'paris_photo_sources.py') --ensure
if($LASTEXITCODE -ne 0){throw 'Verified photographic surface acquisition failed'}
$natureFolder=Join-Path $repo 'unreal\assets\paris-nature'
$natureManifest=Join-Path $natureFolder 'manifest.json'
$needNature=-not(Test-Path -LiteralPath $natureManifest)
if(-not $needNature){
    $nature=Get-Content -LiteralPath $natureManifest -Raw | ConvertFrom-Json
    foreach($file in $nature.files.PSObject.Properties){if(-not(Test-Path -LiteralPath (Join-Path $natureFolder $file.Name))){$needNature=$true}}
}
if($needNature){
    & $python (Join-Path $PSScriptRoot 'fetch_paris_nature.py')
    if($LASTEXITCODE -ne 0){throw 'CC0 nature acquisition failed'}
}
& $python (Join-Path $PSScriptRoot 'generate_paris_architecture.py')
if($LASTEXITCODE -ne 0){throw 'Original architecture generation failed'}
& $python (Join-Path $PSScriptRoot 'generate_paris_street_detail.py')
if($LASTEXITCODE -ne 0){throw 'Original street detail generation failed'}
& $python (Join-Path $PSScriptRoot 'generate_paris_ground_display.py')
if($LASTEXITCODE -ne 0){throw 'Ground display generation failed'}
& $python (Join-Path $PSScriptRoot 'generate_paris_frontages.py')
if($LASTEXITCODE -ne 0){throw 'Source-aligned frontage generation failed'}
foreach($sub in @('Architecture','Street','Ground','Nature\Materials','Nature\Textures','Nature\paris_broadleaf\StaticMeshes','Nature\paris_broadleaf\Materials','Nature\paris_broadleaf\Textures')){
    New-Item -ItemType Directory -Path (Join-Path $repo "unreal\AIWorld\Content\ParisPhotoreal\$sub") -Force | Out-Null
}
foreach($script in @('create-paris-assets.py','bake-paris-photoreal.py','create-paris-nature.py','bake-paris-architecture.py','bake-paris-street-detail.py','bake-paris-ground.py','bake-paris-frontages.py','ensure-paris-nanite-materials.py')){
    $path=Join-Path $PSScriptRoot $script
    & $editor $project '-run=pythonscript' "-script=$path" -CustomConfig=ParisPhotoreal -nullrhi -unattended -nosplash -stdout
    if($LASTEXITCODE -ne 0){throw "Photoreal asset generation failed: $script"}
}
if($ImportCandidate){
    foreach($sub in @('Textures','Materials','StaticMeshes','Meshes')){New-Item -ItemType Directory -Path (Join-Path (Split-Path $project) "Content\ParisPhotoreal\NotreDameCandidate\notre-dame\$sub") -Force | Out-Null}
    $path=Join-Path $PSScriptRoot 'import-notredame-candidate.py'
    & $editor $project '-run=pythonscript' "-script=$path" -nullrhi -unattended -nosplash -stdout
    if($LASTEXITCODE -ne 0){throw 'Notre-Dame candidate import failed; it has not been placed in the scene'}
}
if(-not $SkipScannedFacade -and (Test-Path -LiteralPath (Join-Path (Split-Path $project) 'Content\Data\paris-notredame-scan.json'))){
    & (Join-Path $PSScriptRoot 'Build-NotreDameScan.ps1') -EngineRoot $EngineRoot
}
