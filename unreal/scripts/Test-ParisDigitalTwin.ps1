param([string]$EngineRoot='D:\Epic Games\UE_5.8')
$ErrorActionPreference='Stop'
$project=& (Join-Path $PSScriptRoot 'Get-AIWorldProject.ps1')
$editor=Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$log=Join-Path (Split-Path $project) 'Saved\paris-twin-automation.log'
$argsGIS=@($project,'-game','-ParisTwin','-unattended','-nullrhi','-nosound','-nosplash','-ExecCmds=Automation RunTests ParisDigitalTwin.Live','-TestExit=Automation Test Queue Empty',"-abslog=$log",'-stdout','-UTF8Output')
& $editor @argsGIS
if($LASTEXITCODE -ne 0 -or (Select-String -LiteralPath $log -Pattern 'Result=\{Fail\}|Fatal error' -Quiet) -or -not(Select-String -LiteralPath $log -Pattern 'Result=\{Success\}.*SceneCollisionAndDebug' -Quiet)){throw 'GIS scene/selection/collision automation failed'}
