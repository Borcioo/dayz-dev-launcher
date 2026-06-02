# dzl - DayZ dev launcher : uninstaller
#
#   powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/Borcioo/dayz-dev-launcher/main/uninstall.ps1 | iex"
#   or, from an installed copy:  powershell -ExecutionPolicy Bypass -File uninstall.ps1
#
# Removes the dzl folder and its PATH entry. Asks before deleting, keeps your
# config/presets unless you say otherwise, and never touches Python.

$ErrorActionPreference = 'Stop'

function Info($m) { Write-Host "[..] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "[ok] $m" -ForegroundColor Green }
function Err($m)  { Write-Host "[X]  $m" -ForegroundColor Red }

# Resolve the install dir: the folder this script sits in (when run as a file),
# else $env:DZL_DIR, else the default.
$Dest = $null
if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot 'dzl.bat'))) {
    $Dest = $PSScriptRoot
} elseif ($env:DZL_DIR) {
    $Dest = $env:DZL_DIR
} else {
    $Dest = Join-Path $env:LOCALAPPDATA 'dzl'
}
$Dest = $Dest.TrimEnd('\')

Write-Host ""
Write-Host "==== dzl - DayZ dev launcher : uninstall ====" -ForegroundColor Yellow
Write-Host ""

# Safety: only proceed if this really looks like a dzl install.
if (-not ((Test-Path (Join-Path $Dest 'dzl.bat')) -and (Test-Path (Join-Path $Dest 'launcher')))) {
    Err "No dzl install found at: $Dest"
    Write-Host "    (set \$env:DZL_DIR to your install folder and re-run, or just"
    Write-Host "     delete the folder by hand.)"
    return
}

Write-Host "This will remove:" -ForegroundColor Yellow
Write-Host "    folder : $Dest"
Write-Host "    PATH   : the 'dzl' entry in your user PATH"
$hasData = (Test-Path (Join-Path $Dest 'config.json')) -or (Test-Path (Join-Path $Dest 'presets'))
if ($hasData) { Write-Host "    (your config.json / presets are in that folder)" }
Write-Host ""

$go = Read-Host "Proceed? [y/N]"
if ($go -notmatch '^[Yy]') { Write-Host "Cancelled."; return }

# Optionally preserve config + presets by moving them out before deleting.
if ($hasData) {
    $keep = Read-Host "Keep your config.json and presets (back them up)? [Y/n]"
    if ($keep -notmatch '^[Nn]') {
        $backup = "$Dest-backup"
        $n = 1; while (Test-Path $backup) { $backup = "$Dest-backup-$n"; $n++ }
        New-Item -ItemType Directory -Force -Path $backup | Out-Null
        foreach ($item in 'config.json', 'presets') {
            $src = Join-Path $Dest $item
            if (Test-Path $src) { Move-Item $src $backup }
        }
        Ok "saved your config/presets to: $backup"
    }
}

# --- remove this install's PATH entry (only $Dest) -------------------------
$p = [Environment]::GetEnvironmentVariable('Path', 'User'); if (-not $p) { $p = '' }
$parts = @($p -split ';' | Where-Object { $_ -ne '' })
$keepParts = @($parts | Where-Object { $_.TrimEnd('\') -ne $Dest })
if ($keepParts.Count -ne $parts.Count) {
    [Environment]::SetEnvironmentVariable('Path', ($keepParts -join ';'), 'User')
    Ok "removed dzl from your PATH"
} else {
    Ok "no dzl PATH entry to remove"
}

# --- remove the install folder ---------------------------------------------
# step out of the folder first so it isn't the current directory (which would
# lock the delete), then remove it.
Set-Location -LiteralPath $env:TEMP
Info "Removing $Dest ..."
Remove-Item -Recurse -Force -LiteralPath $Dest
Ok "deleted $Dest"

Write-Host ""
Write-Host "==== dzl uninstalled. (Python was left untouched.) ====" -ForegroundColor Yellow
Write-Host ""
