# MSVC/UBA response files can mishandle Japanese checkout paths; use an ASCII junction.
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$target=Join-Path $repo 'unreal\AIWorld'
$bytes=[Text.Encoding]::UTF8.GetBytes($target)
$hash=[BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($bytes)).Replace('-','').Substring(0,12).ToLowerInvariant()
$parent=Join-Path $env:LOCALAPPDATA 'AIWorldUE'
New-Item -ItemType Directory -Path $parent -Force | Out-Null
$alias=Join-Path $parent $hash
if(Test-Path -LiteralPath $alias){
    $item=Get-Item -LiteralPath $alias
    if($item.LinkType -ne 'Junction' -or $item.Target -ne $target){throw "Build alias belongs to another directory: $alias"}
}else{New-Item -ItemType Junction -Path $alias -Target $target | Out-Null}
Join-Path $alias 'AIWorld.uproject'
