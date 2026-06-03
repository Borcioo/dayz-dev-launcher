# Install the dzl-launcher Claude skill into your user skills folder so any
# Claude Code session can drive the launcher (start/stop/status/logs).
#
#   powershell -ExecutionPolicy Bypass -File skill\install.ps1
#
# Re-run anytime to update. Start a new Claude Code session afterwards to pick
# it up. Uninstall: delete  %USERPROFILE%\.claude\skills\dzl-launcher

$ErrorActionPreference = 'Stop'

$src  = Join-Path $PSScriptRoot 'dzl-launcher'
$dest = Join-Path $HOME '.claude\skills\dzl-launcher'

if (-not (Test-Path (Join-Path $src 'SKILL.md'))) {
    Write-Host "[X] SKILL.md not found next to this script ($src)." -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
Copy-Item -Recurse -Force $src $dest

Write-Host "[ok] Installed the dzl-launcher skill to:" -ForegroundColor Green
Write-Host "     $dest"
Write-Host "Start a new Claude Code session to pick it up." -ForegroundColor Yellow
