$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Test-Path (Join-Path $Root ".git"))) {
    Write-Host "Nincs git repo — a dashboard helyben marad (docs/index.html)."
    exit 0
}

git add docs
$Changed = git diff --cached --name-only -- docs
if (-not $Changed) {
    Write-Host "A dashboard nem valtozott, nincs mit feltolteni."
    exit 0
}

$Stamp = Get-Date -Format "yyyy-MM-dd HH:mm"
git commit -m "Dashboard frissites $Stamp"
git push
