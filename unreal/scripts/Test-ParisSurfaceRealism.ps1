param([string]$EngineRoot='D:\Epic Games\UE_5.8')
$ErrorActionPreference='Stop'
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
if(@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^UnrealEditor(?:-Cmd)?\.exe$' -and $_.CommandLine -like '*AIWorld.uproject*'}).Count){throw 'Close AIWorld before automation'}
$names=@('ReferenceArchitectureAndRestoration','RainLifecycleAndShelter')
$filter=(($names | ForEach-Object {'ParisDigitalTwin.Live.'+$_}) -join '+')
$log=Join-Path (Split-Path $project) 'Saved\paris-surface-realism-automation.log'
$args=@($project,'-game','-ParisTwin','-ParisPhotoreal','-ParisTwinPhotoLook','-CustomConfig=ParisPhotoreal','-nullrhi','-unattended','-nosplash',('-ExecCmds=Automation RunTests '+$filter),'-TestExit=Automation Test Queue Empty',('-abslog='+$log),'-stdout','-UTF8Output')
& (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe') @args
if($LASTEXITCODE -ne 0 -or (Select-String -LiteralPath $log -Pattern 'Result=\{Fail\}|Fatal error|PARIS_REFERENCE_INVALID|PARIS_REFERENCE_MISSING' -Quiet)){throw 'Surface realism automation failed'}
foreach($name in $names){if(-not(Select-String -LiteralPath $log -Pattern ('Result=\{Success\}.*Name=\{'+$name+'\}') -Quiet)){throw ('Test did not complete '+$name)}}
