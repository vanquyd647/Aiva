$ErrorActionPreference = "Stop"

$pythonCmd = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $pythonCmd)) {
    $pythonCmd = "python"
}

Write-Host "Applying Alembic migrations (upgrade head)..."
& $pythonCmd -m alembic -c backend/alembic.ini upgrade head
if ($LASTEXITCODE -ne 0) {
    throw "Migration failed with exit code $LASTEXITCODE"
}

Write-Host "Database migration completed."
