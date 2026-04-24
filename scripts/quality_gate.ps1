param(
    [switch]$SkipStyleChecks
)

$ErrorActionPreference = "Stop"

$pythonCmd = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $pythonCmd)) {
    $pythonCmd = "python"
}

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    Write-Host $Name
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

if (-not $SkipStyleChecks) {
    Invoke-Step "[1/5] Ruff lint" { & $pythonCmd -m ruff check backend backend/tests app.py admin_app.py core scripts/validate_change_docs.py }
    Invoke-Step "[2/5] Black format check" { & $pythonCmd -m black --check backend backend/tests scripts/validate_change_docs.py }
} else {
    Write-Host "[1/5] Style checks skipped (SkipStyleChecks switch enabled)."
}

Invoke-Step "[3/5] Doc update guard" { & $pythonCmd scripts/validate_change_docs.py }
Invoke-Step "[4/5] Pytest" { & $pythonCmd -m pytest backend/tests }
Invoke-Step "[5/5] Compile smoke test" { & $pythonCmd -m compileall backend app.py admin_app.py core scripts }

Write-Host "Quality gate passed."
