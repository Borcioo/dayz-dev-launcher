# Put $Dir on the user PATH for the 'dzl' command, removing any previous dzl
# install entries first (so a reinstall / moved folder never leaves duplicates).
param([Parameter(Mandatory = $true)][string]$Dir)

$Dir = (Resolve-Path $Dir).Path.TrimEnd('\')
$p = [Environment]::GetEnvironmentVariable('Path', 'User'); if (-not $p) { $p = '' }
$parts = @($p -split ';' | Where-Object { $_ -ne '' })

# a "dzl install" entry = a folder that holds dzl.bat and the launcher package
$stale = @($parts | Where-Object {
    $_ -ne $Dir -and (Test-Path (Join-Path $_ 'dzl.bat')) -and (Test-Path (Join-Path $_ 'launcher'))
})
if ($stale.Count) {
    Write-Host "Found a previous dzl on your PATH:" -ForegroundColor Yellow
    $stale | ForEach-Object { Write-Host "    $_" }
    $ans = Read-Host "    Remove the old entr(y/ies) and use $Dir ? [Y/n]"
    if ($ans -eq '' -or $ans -match '^[Yy]') {
        $parts = @($parts | Where-Object { $_ -notin $stale })
        Write-Host "[ok] removed old PATH entr(y/ies)" -ForegroundColor Green
    }
}

if ($parts -notcontains $Dir) { $parts += $Dir }
$new = ($parts -join ';')
if ($new -ne $p) {
    [Environment]::SetEnvironmentVariable('Path', $new, 'User')
    Write-Host "[ok] PATH updated -> $Dir" -ForegroundColor Green
} else {
    Write-Host "[ok] PATH already correct" -ForegroundColor Green
}
