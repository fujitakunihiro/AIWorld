param([string]$EngineRoot='D:\Epic Games\UE_5.8', [string]$ServerURL='')
$ErrorActionPreference='Stop'
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$log=Join-Path (Split-Path $project) 'Saved\native-automation.log'
$argsNative=@($project,'-game','-unattended','-nullrhi','-nosound','-nosplash','-ExecCmds=Automation RunTests AIWorld','-TestExit=Automation Test Queue Empty',"-abslog=$log",'-stdout','-UTF8Output')
if($ServerURL){$argsNative+="-AIWorldServer=$ServerURL"}
& $editor @argsNative
if($LASTEXITCODE -ne 0 -or (Select-String -LiteralPath $log -Pattern 'Result=\{Fail\}|Fatal error' -Quiet)){throw 'Native automation failed'}
