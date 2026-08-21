$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

$Stagger = $true
$Forward = @()
foreach ($Arg in $args) {
    if ($Arg -eq "-NoDelay") { $Stagger = $false }
    else { $Forward += $Arg }
}

$LogDir = Join-Path $Root "data"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir "collect.log"
$Stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $Log -Value "`n==== $Stamp collect ====" -Encoding utf8

if ($Stagger) {
    $WaitSec = Get-Random -Minimum 180 -Maximum 1081
    $Msg = "Veletlen kesleltetes: $WaitSec masodperc (~$([math]::Round($WaitSec/60, 1)) perc), hogy ne 10:00-kor pontosan induljon."
    Write-Host $Msg
    Add-Content -Path $Log -Value $Msg -Encoding utf8
    Start-Sleep -Seconds $WaitSec
}

& $Python -m farewatch collect @Forward *>&1 | Tee-Object -FilePath $Log -Append
$CollectExit = $LASTEXITCODE

& $Python -m farewatch dashboard *>&1 | Tee-Object -FilePath $Log -Append
$Publish = Join-Path $PSScriptRoot "publish-dashboard.ps1"
if (Test-Path $Publish) {
    & $Publish *>&1 | Tee-Object -FilePath $Log -Append
}

exit $CollectExit
