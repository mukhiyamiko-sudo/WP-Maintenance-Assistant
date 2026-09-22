param([string]$Python = "python")

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root
try {
    & $Python -m PyInstaller --clean --noconfirm --onefile --windowed `
        --name HostingerWordPressMaintenanceToolkit `
        --collect-submodules selenium `
        app.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
    Write-Host "Built: $Root\dist\HostingerWordPressMaintenanceToolkit.exe"
}
finally {
    Pop-Location
}
