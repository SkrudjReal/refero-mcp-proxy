<#
.SYNOPSIS
    Refero MCP Proxy — Automated Installer for Windows
    Configures Codex, Antigravity, Claude Code, and OpenCode safely.

.PARAMETER Clients
    One or more AI clients to configure: 'all', 'codex', 'antigravity', 'claude', 'opencode'. Default: 'all'.

.PARAMETER DataDir
    Path to custom REFERO_DATA_DIR containing mirrored dataset (also used as --dest when -Unpack is set).

.PARAMETER Offline
    Enforce REFERO_OFFLINE=1 in client configurations for 100% air-gapped operation.

.PARAMETER Unpack
    Extract downloaded refero_*.zip archives into the expected dataset directory.

.PARAMETER UnpackSrc
    Optional directory containing downloaded refero_*.zip archives (used with -Unpack).

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
    [switch]$Unpack,
    [string]$UnpackSrc = "",
    [switch]$Remove,
    [switch]$Status
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " Refero MCP Proxy — Automated Client Installer (Windows)" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Detect Python (prefer real python.exe over WindowsApps stub)
$PythonBin = ""
try {
    $found = @(Get-Command "python.exe" -CommandType Application -ErrorAction SilentlyContinue | Where-Object { $_.Source -notmatch "WindowsApps" })
    if ($found.Count -gt 0) {
        $PythonBin = $found[0].Source
    }
} catch {}

if (-not $PythonBin) {
    $Candidates = @(Get-ChildItem -Path "$env:LOCALAPPDATA\Python\*" -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue)
    if ($Candidates.Count -gt 0) {
        $PythonBin = $Candidates[0].FullName
    }
}

if (-not $PythonBin) {
    try {
        $fallback = @(Get-Command "python.exe" -CommandType Application -ErrorAction SilentlyContinue)
        if ($fallback.Count -gt 0) {
            $PythonBin = $fallback[0].Source
        }
    } catch {}
}

if (-not $PythonBin) {
    Write-Host "[ERROR] python.exe was not found on PATH or common Windows directories." -ForegroundColor Red
    Write-Host "Install Python 3.8+ from https://www.python.org." -ForegroundColor Yellow
    exit 1
}

$PyVer = (& $PythonBin -c "import sys; print(str(sys.version_info[0]) + '.' + str(sys.version_info[1]))").Trim()
Write-Host "Found Python: $PythonBin (v$PyVer)" -ForegroundColor DarkGray

# Check Python >= 3.8
& $PythonBin -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Python 3.8 or higher is required. Found v$PyVer." -ForegroundColor Red
    exit 1
}

# 2. Handle Status early
if ($Status) {
    & $PythonBin "$ScriptDir\configure_clients.py" --status
    exit $LASTEXITCODE
}

# 3. Check & install Pillow (optional for stitching; relax ErrorActionPreference for native stderr)
Write-Host ""
Write-Host "[1/3] Checking optional dependencies..." -ForegroundColor Cyan
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $PythonBin -c "import PIL" 2>$null
$pilExit = $LASTEXITCODE
if ($pilExit -eq 0) {
    Write-Host "  [OK] Pillow is already installed (image stitching enabled)." -ForegroundColor Green
} else {
    Write-Host "  [INFO] Pillow not found. Installing Pillow for screenshot stitching..." -ForegroundColor Yellow
    & $PythonBin -m pip install Pillow --quiet 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [WARN] Could not install Pillow automatically; basic operations still work." -ForegroundColor DarkGray
    }
}
$ErrorActionPreference = $prevEAP

# 4. Handle Unpack (also trigger if -UnpackSrc was supplied directly)
if ($Unpack -or $UnpackSrc) {
    Write-Host ""
    Write-Host "[Unpack] Running Refero dataset extractor..." -ForegroundColor Cyan
    $UnpackArgs = @("$ScriptDir\unpack_dataset.py")
    if ($UnpackSrc) {
        $UnpackArgs += @("--src", "$UnpackSrc")
    }
    if ($DataDir) {
        $UnpackArgs += @("--dest", "$DataDir")
    }
    & $PythonBin $UnpackArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Dataset unpacking failed (exit code $LASTEXITCODE)." -ForegroundColor Red
        exit $LASTEXITCODE
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
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Client configuration failed (exit code $LASTEXITCODE)." -ForegroundColor Red
    exit $LASTEXITCODE
}

# 7. Final status verification
Write-Host ""
Write-Host "[3/3] Installation Verification:" -ForegroundColor Cyan
& $PythonBin "$ScriptDir\configure_clients.py" --status

Write-Host ""
Write-Host "==================================================================" -ForegroundColor Green
Write-Host " Installation Complete!" -ForegroundColor Green
Write-Host " Restart or reload your AI assistant (Codex, Antigravity, Claude, OpenCode)." -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
Write-Host ""
