$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Eloszor hozz letre a .venv-et: python -m venv .venv"
}

$TaskName = "Farewatch-BUD-MAD"
$CollectScript = Join-Path $Root "scripts\collect.ps1"
$BackupScript = Join-Path $Root "scripts\backup-db.ps1"
$CollectAction = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$CollectScript`""
$BackupAction = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$BackupScript`""

schtasks /Create /TN $TaskName /SC DAILY /ST 06:00 /TR $CollectAction /F
if ($LASTEXITCODE -ne 0) { throw "Nem sikerult a gyujto feladatot letrehozni" }

schtasks /Create /TN "$TaskName-backup" /SC DAILY /ST 06:40 /TR $BackupAction /F
if ($LASTEXITCODE -ne 0) { throw "Nem sikerult a backup feladatot letrehozni" }

Write-Host "Kesz: napi 06:00 collect, 06:40 backup."
Write-Host "Ellenorzes: schtasks /Query /TN $TaskName /V /FO LIST"
