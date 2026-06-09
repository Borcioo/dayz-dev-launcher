# dzl - DayZ dev launcher : web installer
#
#   powershell -c "irm https://raw.githubusercontent.com/Borcioo/dayz-dev-launcher/main/install.ps1 | iex"
#
# Checks Python, downloads dzl to %LOCALAPPDATA%\dzl, sets up the venv and
# dependencies, and adds it to your PATH. No admin required.

$ErrorActionPreference = 'Stop'
$RepoGit = 'https://github.com/Borcioo/dayz-dev-launcher.git'
$RepoZip = 'https://github.com/Borcioo/dayz-dev-launcher/archive/refs/heads/main.zip'
# install location: override with  $env:DZL_DIR='D:\tools\dzl'  before running.
$Dest = if ($env:DZL_DIR) { $env:DZL_DIR } else { Join-Path $env:LOCALAPPDATA 'dzl' }

function Info($m) { Write-Host "[..] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "[ok] $m" -ForegroundColor Green }
function Err($m)  { Write-Host "[X]  $m" -ForegroundColor Red }

# Run a native command (git/python/pip/winget) tolerating its stderr — under
# 'Stop', stderr from a native exe would otherwise be raised as an error even
# on success. We check the real exit code instead.
function Native {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $args[0] @($args[1..($args.Count - 1)]) 2>&1 | ForEach-Object { Write-Host $_ } }
    finally { $ErrorActionPreference = $prev }
    if ($LASTEXITCODE -ne 0) { throw ("command failed ($LASTEXITCODE): " + ($args -join ' ')) }
}

Write-Host ""
Write-Host "==== dzl - DayZ dev launcher : installer ====" -ForegroundColor Yellow
Write-Host ""

# --- 1) Python 3.11+ --------------------------------------------------------
function Test-Python {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) { return $false }
    & python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" 2>$null
    return ($LASTEXITCODE -eq 0)
}

if (-not (Test-Python)) {
    Err "Python 3.11+ was not found."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        $ans = Read-Host "    Install Python 3.12 now via winget? [Y/n]"
        if ($ans -eq '' -or $ans -match '^[Yy]') {
            Info "Installing Python 3.12 via winget ..."
            Native winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
            Write-Host ""
            Ok "Python installed. CLOSE this terminal, open a new one, and run the installer again."
            return
        }
    }
    Write-Host "    Install Python 3.11+ from https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "    (tick 'Add python.exe to PATH'), then run this installer again." -ForegroundColor Yellow
    return
}
Ok ("Python " + (& python -c "import sys;print('.'.join(map(str,sys.version_info[:3])))"))

# --- 2) fetch the app -------------------------------------------------------
# config.json / presets\ are the user's local setup (gitignored). The git-pull
# update path never touches them, but the replace paths (re-clone / ZIP) wipe
# $Dest — so stash them aside and put them back after the swap.
function Save-UserData {
    if (-not (Test-Path $Dest)) { return $null }
    $keep = Join-Path $env:TEMP ("dzl-keep-" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $keep | Out-Null
    foreach ($item in 'config.json', 'presets') {
        $p = Join-Path $Dest $item
        if (Test-Path $p) { Copy-Item -Recurse $p (Join-Path $keep $item) }
    }
    return $keep
}
function Restore-UserData($keep) {
    if (-not $keep) { return }
    Get-ChildItem $keep | ForEach-Object { Copy-Item -Recurse -Force $_.FullName $Dest }
    Remove-Item -Recurse -Force $keep
}

$haveGit = [bool](Get-Command git -ErrorAction SilentlyContinue)
if ((Test-Path (Join-Path $Dest '.git')) -and $haveGit) {
    Info "Updating existing install in $Dest ..."
    Native git -C $Dest pull --ff-only
} elseif ($haveGit) {
    $keep = Save-UserData
    if (Test-Path $Dest) { Remove-Item -Recurse -Force $Dest }
    Info "Cloning into $Dest ..."
    Native git clone --depth 1 $RepoGit $Dest
    Restore-UserData $keep
} else {
    Info "Downloading to $Dest (no git found, using ZIP) ..."
    $tmp = Join-Path $env:TEMP ("dzl-" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    $zip = Join-Path $tmp 'dzl.zip'
    Invoke-WebRequest -Uri $RepoZip -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    $inner = Get-ChildItem -Directory $tmp | Where-Object { $_.Name -like 'dayz-dev-launcher-*' } | Select-Object -First 1
    $keep = Save-UserData
    if (Test-Path $Dest) { Remove-Item -Recurse -Force $Dest }
    Move-Item $inner.FullName $Dest
    Restore-UserData $keep
    Remove-Item -Recurse -Force $tmp
}
Ok "App in $Dest"

# --- 3) venv + dependencies -------------------------------------------------
$venvPy = Join-Path $Dest '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
    Info "Creating virtual environment ..."
    Native python -m venv (Join-Path $Dest '.venv')
}
Info "Installing dependencies ..."
Native $venvPy -m pip install --upgrade pip
Native $venvPy -m pip install -r (Join-Path $Dest 'requirements.txt')
Ok "Dependencies installed"

# --- 4) PATH (user scope) — shared logic, dedups previous installs ----------
& (Join-Path $Dest '_path.ps1') -Dir $Dest

Write-Host ""
Write-Host "==== Done! Open a NEW terminal and run:  dzl ====" -ForegroundColor Yellow
Write-Host ""
