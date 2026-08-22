$ErrorActionPreference = "Continue"
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

function Write-Log {
    param([string]$Message)
    $Line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
    Write-Host $Line
    try {
        Add-Content -Path $Log -Value $Line -Encoding utf8 -ErrorAction SilentlyContinue
    } catch {
    }
}

function Invoke-Farewatch {
    param([string[]]$PyArgs)
    Write-Log ("INDUL: " + $Python + " " + ($PyArgs -join " "))
    $Stdout = Join-Path $LogDir "last-stdout.txt"
    $Stderr = Join-Path $LogDir "last-stderr.txt"
    Remove-Item -Path $Stdout, $Stderr -ErrorAction SilentlyContinue
    $Proc = Start-Process -FilePath $Python -ArgumentList $PyArgs -WorkingDirectory $Root `
        -Wait -PassThru -NoNewWindow `
        -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr
    foreach ($Part in @($Stdout, $Stderr)) {
        if (Test-Path $Part) {
            Get-Content -Path $Part -ErrorAction SilentlyContinue | ForEach-Object { Write-Log $_ }
        }
    }
    $Code = $Proc.ExitCode
    if ($null -eq $Code) { $Code = 1 }
    Write-Log "KILEPES: $Code"
    return $Code
}

Write-Log "==== collect ===="

if ($Stagger) {
    $WaitSec = Get-Random -Minimum 180 -Maximum 1081
    Write-Log "Veletlen kesleltetes: $WaitSec masodperc (~$([math]::Round($WaitSec/60, 1)) perc)"
    Start-Sleep -Seconds $WaitSec
    Write-Log "Kesleltetes vege, collect indul."
}

$CollectArgs = @("-m", "farewatch", "collect") + $Forward
$CollectExit = Invoke-Farewatch -PyArgs $CollectArgs
Invoke-Farewatch -PyArgs @("-m", "farewatch", "dashboard") | Out-Null

$Publish = Join-Path $PSScriptRoot "publish-dashboard.ps1"
if (Test-Path $Publish) {
    Write-Log "INDUL: publish-dashboard.ps1"
    try {
        & $Publish *>&1 | ForEach-Object { Write-Log ([string]$_) }
        Write-Log "KILEPES publish: $LASTEXITCODE"
    } catch {
        Write-Log ("HIBA publish: " + $_.Exception.Message)
    }
}

exit $CollectExit
