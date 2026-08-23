$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Eloszor hozz letre a .venv-et: python -m venv .venv"
}

$CollectScript = Join-Path $Root "scripts\collect.ps1"
$BackupScript = Join-Path $Root "scripts\backup-db.ps1"
$CollectArg = "-NoProfile -ExecutionPolicy Bypass -File `"$CollectScript`""
$BackupArg = "-NoProfile -ExecutionPolicy Bypass -File `"$BackupScript`""

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -MultipleInstances IgnoreNew

$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

function Install-DailyTask {
    param(
        [string]$Name,
        [string]$Argument,
        [datetime]$At
    )
    $Action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument $Argument `
        -WorkingDirectory $Root
    $Trigger = New-ScheduledTaskTrigger -Daily -At $At
    Register-ScheduledTask `
        -TaskName $Name `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Force | Out-Null
}

Install-DailyTask -Name "Farewatch-BUD-MAD" -Argument $CollectArg -At ([datetime]"10:00")
Install-DailyTask -Name "Farewatch-BUD-MAD-retry" -Argument $CollectArg -At ([datetime]"12:00")
Install-DailyTask -Name "Farewatch-BUD-MAD-backup" -Argument $BackupArg -At ([datetime]"12:40")
$CollectArgPdl = "$CollectArg --scope stay"
Install-DailyTask -Name "Farewatch-BUD-PDL" -Argument $CollectArgPdl -At ([datetime]"15:00")
Install-DailyTask -Name "Farewatch-BUD-PDL-retry" -Argument $CollectArgPdl -At ([datetime]"17:00")

Write-Host "Kesz. Laptopon, bejelentkezve:"
Write-Host "  10:00  Farewatch-BUD-MAD         gyujtes + dashboard + git push"
Write-Host "  12:00  Farewatch-BUD-MAD-retry   hibas keresesek ujra, HTML + push"
Write-Host "  12:40  Farewatch-BUD-MAD-backup  SQLite masolat"
Write-Host "  15:00  Farewatch-BUD-PDL         Azori 7 ej naptar (scope stay)"
Write-Host "  17:00  Farewatch-BUD-PDL-retry   hibas PDL keresesek ujra"
Write-Host "Ha 10:00-kor a gep meg ki van, bejelentkezes utan a StartWhenAvailable elinditja."
Write-Host "Ellenorzes:  Get-ScheduledTask -TaskName 'Farewatch-*'"
