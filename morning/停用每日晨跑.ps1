param([string]$MorningDirectory = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
$taskName = 'VirtualRun-Morning-0700'
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
    $expectedLauncher = Join-Path $MorningDirectory '启动晨跑.ps1'
    $ownedDescription = $task.Description -like 'Prepare emulator at 06:55;*' -or $task.Description -like 'Prepare emulator at 06:25;*' -or $task.Description -like 'Prepare emulator at 06:00;*'
    if (!$ownedDescription -or
        @($task.Actions | Where-Object { $_.Arguments -like ('*"' + $expectedLauncher + '"*') }).Count -ne 1) {
        throw 'The task does not belong to this installation; it was not changed.'
    }
    # Disabling future runs does not abruptly kill an in-progress run.
    Disable-ScheduledTask -TaskName $taskName | Out-Null
    Write-Output 'Future daily runs disabled. An active run will finish normally.'
} else { Write-Output 'No daily task is installed.' }
