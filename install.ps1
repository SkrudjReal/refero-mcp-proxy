<#
.SYNOPSIS
    Refero MCP Proxy — Automated Installer for Windows
    Configures Codex, Antigravity, Claude Code, and OpenCode seamlessly.

.PARAMETER Clients
    One or more AI clients to configure: 'all', 'codex', 'antigravity', 'claude', 'opencode'. Default: 'all'.

.PARAMETER DataDir
    Path to custom REFERO_DATA_DIR containing mirrored dataset (fleet/images, fleet/flows, styles).

.PARAMETER Offline
    Enforce REFERO_OFFLINE=1 in client configurations for 100% air-gapped operation.

.PARAMETER Unpack
    Extract downloaded refero_*.zip archives into the expected dataset directory.

.PARAMETER Remove
    Uninstall/remove refero MCP server from selected clients.

.PARAMETER Status
    Inspect current configuration status without modifying files.
#>

[CmdletBinding()]
param(
    [string[]]$Clients = @("all"),
    [string]$DataDir = "",
    [switch]$Offline,
    [string]$Unpack = "",
    [switch]$Remove,
    [switch]$Status
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " ✦ Refero MCP Proxy — Automated Client Installer (Windows)" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Detect Python
$PythonBin = ""
try {
    $found = Get-Command "python.exe" -CommandType Application -ErrorAction SilentlyContinue | Where-Object { $_.Source -notmatch "WindowsApps" }
    if ($found) {
        $PythonBin = $found[0].Source
    }
} catch {}

if (-not $PythonBin) {
    # Check common LocalAppData paths
    $Candidates = Get-ChildItem -Path "$env:LOCALAPPDATA\Python\*" -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue
    if ($Candidates) {
        $PythonBin = $Candidates[0].FullName
    }
}

if (-not $PythonBin) {
    try {
        $PythonBin = (Get-Command "python.exe" -ErrorAction SilentlyContinue).Source
    } catch {}
}

if (-not $PythonBin) {
    Write-Host "❌ Error: python.exe was not found on PATH or common Windows directories." -ForegroundColor Red
    Write-Host "Please install Python 3.8+ from https://www.python.org or the Microsoft Store." -ForegroundColor Yellow
    exit 1
}

$PyVer = (& $PythonBin -c "import sys; print(str(sys.version_info[0]) + '.' + str(sys.version_info[1]))").Trim()
Write-Host "Found Python: $PythonBin (v$PyVer)" -ForegroundColor DarkGray

# Check Python >= 3.8
& $PythonBin -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)'
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error: Python 3.8 or higher is required. Found v$PyVer." -ForegroundColor Red
    exit 1
}

# 2. Check & install Pillow (optional for stitching)
Write-Host ""
Write-Host "[1/3] Checking optional dependencies..." -ForegroundColor Cyan
& $PythonBin -c "import PIL" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✔ Pillow is already installed (image stitching enabled)." -ForegroundColor Green
} else {
    Write-Host "  ℹ Pillow not found. Installing Pillow for screenshot stitching..." -ForegroundColor Yellow
    & $PythonBin -m pip install Pillow --quiet 2>$null
}

# 3. Handle Status
if ($Status) {
    & $PythonBin "$ScriptDir\configure_clients.py" --status
    exit 0
}

# 4. Handle Unpack
if ($PSBoundParameters.ContainsKey('Unpack')) {
    Write-Host ""
    Write-Host "[Unpack] Running Refero dataset extractor..." -ForegroundColor Cyan
    if ($Unpack -and $Unpack -ne "True") {
        & $PythonBin "$ScriptDir\unpack_dataset.py" --src "$Unpack"
    } else {
        & $PythonBin "$ScriptDir\unpack_dataset.py"
    }
}

# 5. Build arguments for configure_clients.py
$ConfigArgs = @("$ScriptDir\configure_clients.py", "--python", "$PythonBin")

if ($Clients) {
    $ConfigArgs += "--clients"
    foreach ($c in $Clients) {
        $parts = $c -split ","
        foreach ($p in $parts) {
            $trimmed = $p.Trim()
            if ($trimmed) {
                $ConfigArgs += $trimmed
            }
        }
    }
}

if ($DataDir) {
    $ConfigArgs += @("--data-dir", "$DataDir")
}

if ($Offline) {
    $ConfigArgs += "--offline"
}

if ($Remove) {
    $ConfigArgs += "--remove"
}

# 6. Execute configuration
Write-Host ""
Write-Host "[2/3] Configuring AI Coding Clients..." -ForegroundColor Cyan
& $PythonBin $ConfigArgs

# 7. Final status verification
Write-Host ""
Write-Host "[3/3] Installation Verification:" -ForegroundColor Cyan
& $PythonBin "$ScriptDir\configure_clients.py" --status

Write-Host ""
Write-Host "==================================================================" -ForegroundColor Green
Write-Host " ✦ Installation Complete!" -ForegroundColor Green
Write-Host " Restart or reload your AI assistant (Codex, Antigravity, Claude, OpenCode)." -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
Write-Host ""
