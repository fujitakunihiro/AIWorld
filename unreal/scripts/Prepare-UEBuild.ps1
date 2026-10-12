# Install-free, per-user image of the official .NET Framework SDK required by UBT.
# Existing system SDKs take precedence. Downloads are pinned to Microsoft's VS manifest hashes.
$ErrorActionPreference='Stop'
foreach($prefix in @('HKCU:\SOFTWARE','HKCU:\SOFTWARE\WOW6432Node','HKLM:\SOFTWARE','HKLM:\SOFTWARE\WOW6432Node')) {
    foreach($key in (Get-ChildItem "$prefix\Microsoft\Microsoft SDKs\NETFXSDK" -ErrorAction SilentlyContinue)) {
        $p=(Get-ItemProperty $key.PSPath -ErrorAction SilentlyContinue).KitsInstallationFolder
        if($p -and (Test-Path -LiteralPath (Join-Path $p 'Include\um\mscoree.h'))){return}
    }
}
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$sdkdir=Join-Path $repo 'unreal\.toolchain\netfx48'
New-Item -ItemType Directory -Path $sdkdir -Force | Out-Null
$base='https://download.visualstudio.microsoft.com/download/pr/33ce7103-7284-4a6b-9efc-a889c13bdcbb/'
$files=@(
    @{Name='sdk_tools48.msi';Hash='61c76da293738f93fd0176837e5e70bf414903ecb527a7fc25fc7c862066f5bc'},
    @{Name='sdk_tools48.cab';Hash='131fa7cd8d661a151a13077a4bed21a4d187c5070b223c28fcf1a2bd1243d817'}
)
foreach($f in $files){
    $dest=Join-Path $sdkdir $f.Name
    if(-not(Test-Path -LiteralPath $dest)){Invoke-WebRequest -Uri ($base+$f.Hash+'/'+$f.Name) -OutFile $dest}
    if((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash -ne $f.Hash){throw 'SDK hash mismatch'}
}
$msi=Join-Path $sdkdir 'sdk_tools48.msi'
$extract=Join-Path $sdkdir 'extracted'
$p=Start-Process msiexec.exe -ArgumentList @('/a',('"'+$msi+'"'),'/qn',('TARGETDIR="'+$extract+'"')) -WindowStyle Hidden -Wait -PassThru
if($p.ExitCode -ne 0){throw "SDK image extraction failed: $($p.ExitCode)"}
$header=Get-ChildItem -LiteralPath $extract -Filter mscoree.h -Recurse | Select-Object -First 1
if(-not $header){throw 'SDK header not found'}
$sdkroot=Split-Path (Split-Path (Split-Path $header.FullName -Parent) -Parent) -Parent
if(-not(Test-Path -LiteralPath (Join-Path $sdkroot 'Lib\um\x64\mscoree.lib'))){throw 'SDK library not found'}
$reg='HKCU:\SOFTWARE\Microsoft\Microsoft SDKs\NETFXSDK\4.8'
New-Item -Path $reg -Force | Out-Null
New-ItemProperty -Path $reg -Name KitsInstallationFolder -Value $sdkroot -PropertyType String -Force | Out-Null
Write-Output "Prepared local .NET Framework SDK: $sdkroot"
