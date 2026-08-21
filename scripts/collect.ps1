$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

& $Python -m farewatch collect @args
$CollectExit = $LASTEXITCODE

& $Python -m farewatch dashboard
$Publish = Join-Path $PSScriptRoot "publish-dashboard.ps1"
if (Test-Path $Publish) {
    & $Publish
}

exit $CollectExit
