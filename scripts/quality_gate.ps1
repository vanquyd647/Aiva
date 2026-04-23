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
    Invoke-Step "[1/4] Ruff lint" { & $pythonCmd -m ruff check backend backend/tests app.py admin_app.py assistant.py core }
    Invoke-Step "[2/4] Black format check" { & $pythonCmd -m black --check backend backend/tests }
} else {
    Write-Host "[1/4] Style checks skipped (SkipStyleChecks switch enabled)."
}

Invoke-Step "[3/4] Pytest" { & $pythonCmd -m pytest backend/tests }
Invoke-Step "[4/4] Compile smoke test" { & $pythonCmd -m compileall backend app.py admin_app.py assistant.py core }

Write-Host "Quality gate passed."
