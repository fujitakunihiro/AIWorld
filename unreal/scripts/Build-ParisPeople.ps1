param([string]$EngineRoot='D:\Epic Games\UE_5.8',[switch]$Offline)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python=Join-Path $repo 'gis\.venv\Scripts\python.exe'
$options=@(); if($Offline){$options+='--offline'}
& $python (Join-Path $PSScriptRoot 'fetch_paris_people.py') @options
if($LASTEXITCODE -ne 0){throw 'Pedestrian source verification failed'}
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
foreach($folder in @('Textures','Materials','Male_Adult_01','Female_Adult_01')){
    New-Item -ItemType Directory -Path (Join-Path $repo ('unreal\AIWorld\Content\ParisPhotoreal\People\'+$folder)) -Force | Out-Null
}
$editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$script=Join-Path $PSScriptRoot 'bake-paris-people.py'
$log=Join-Path (Split-Path $project) 'Saved\paris-people-bake.log'
& $editor $project '-run=pythonscript' "-script=$script" '-unattended' '-nullrhi' '-nosplash' '-stdout' '-UTF8Output' "-abslog=$log"
if($LASTEXITCODE -ne 0 -or -not(Select-String -LiteralPath $log -Pattern 'PARIS_PEOPLE_READY 2' -Quiet)){
    throw 'Pedestrian skeletal import failed; see Saved/paris-people-bake.log'
}
$packet=Get-Content -LiteralPath (Join-Path (Split-Path $project) 'Content\Data\paris-people.json') -Raw | ConvertFrom-Json
foreach($avatar in $packet.avatars){
    if($avatar.lod_vertices.Count -ne 3 -or $avatar.height_cm -lt 150 -or $avatar.height_cm -gt 200){throw 'Pedestrian LODs or physical scale are invalid'}
    $references=@($avatar.mesh,$avatar.skeleton)+@($avatar.animations.PSObject.Properties | ForEach-Object {$_.Value})
    foreach($reference in $references){
        $file=Join-Path (Split-Path $project) ('Content\'+($reference -split '\.')[0].Substring(6)+'.uasset')
        if(-not(Test-Path -LiteralPath $file)){throw "Imported pedestrian dependency was not saved: $reference"}
    }
}
