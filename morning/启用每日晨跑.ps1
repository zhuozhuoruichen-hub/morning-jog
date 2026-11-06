$ErrorActionPreference = 'Stop'
$taskName = 'VirtualRun-Morning-0700'
$launcherPath = Join-Path $PSScriptRoot '启动晨跑.ps1'
$runnerPath = Join-Path $PSScriptRoot 'morning_run.py'
if (!(Test-Path -LiteralPath $runnerPath)) { throw 'Missing morning runner script.' }
$config = Get-Content -LiteralPath (Join-Path $PSScriptRoot '晨跑配置.json') -Encoding UTF8 -Raw | ConvertFrom-Json
if (!(Test-Path -LiteralPath $config.python)) { throw 'Configured Python interpreter was not found.' }
if ((Get-TimeZone).Id -ne 'China Standard Time') { throw 'Set Windows time zone to China Standard Time first.' }
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    $ownedDescription = $existingTask.Description -like 'Prepare emulator at 06:55;*' -or $existingTask.Description -like 'Prepare emulator at 06:25;*' -or $existingTask.Description -like 'Prepare emulator at 06:00;*'
    $ownedAction = @($existingTask.Actions | Where-Object { $_.Arguments -like ('*"' + $launcherPath + '"*') }).Count -eq 1
    if (!$ownedDescription -or !$ownedAction) {
        throw 'A task with this name already exists and is not owned by this application.'
    }
}
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $launcherPath + '"') -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -Daily -At '06:00'
$deadline = if ($config.task_deadline) { [datetime]::ParseExact($config.task_deadline, 'yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture) } else { [datetime]'2026-11-30' }
$trigger.EndBoundary = $deadline.AddDays(1).ToString('yyyy-MM-ddTHH:mm:ss')
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 150) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Prepare emulator at 06:00; run Anxiaoxin from 06:30 to 08:00 Beijing time. Finish at 3 km; check settlement. Ends 2026-11-30.'
Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
Get-ScheduledTaskInfo -TaskName $taskName | Select-Object TaskName,NextRunTime,LastTaskResult
