param(
    [switch]$SkipInstallerInstall,
    [string]$OutputDir = "dist/desktop"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$pythonCmd = Join-Path $repoRoot ".venv\Scripts\python.exe"
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

if (-not $SkipInstallerInstall) {
    Invoke-Step "[1/3] Install PyInstaller" { & $pythonCmd -m pip install --upgrade pyinstaller }
} else {
    Write-Host "[1/3] Skip PyInstaller installation (SkipInstallerInstall switch enabled)."
}

$outputPath = Join-Path $repoRoot $OutputDir
$buildRoot = Join-Path $repoRoot "build/pyinstaller"
$specPath = Join-Path $buildRoot "spec"
$userWorkPath = Join-Path $buildRoot "user"
$adminWorkPath = Join-Path $buildRoot "admin"

New-Item -ItemType Directory -Path $outputPath -Force | Out-Null
New-Item -ItemType Directory -Path $specPath -Force | Out-Null
New-Item -ItemType Directory -Path $userWorkPath -Force | Out-Null
New-Item -ItemType Directory -Path $adminWorkPath -Force | Out-Null

Remove-Item (Join-Path $outputPath "AIAssistUser.exe") -ErrorAction SilentlyContinue
Remove-Item (Join-Path $outputPath "AIAssistAdmin.exe") -ErrorAction SilentlyContinue

$commonArgs = @(
    "--noconfirm"
    "--clean"
    "--onefile"
    "--windowed"
    "--collect-all"
    "customtkinter"
    "--specpath"
    $specPath
    "--distpath"
    $outputPath
)

Invoke-Step "[2/3] Build user desktop executable" {
    & $pythonCmd -m PyInstaller @commonArgs `
        "--workpath" $userWorkPath `
        "--name" "AIAssistUser" `
        "app.py"
}

Invoke-Step "[3/3] Build admin desktop executable" {
    & $pythonCmd -m PyInstaller @commonArgs `
        "--workpath" $adminWorkPath `
        "--name" "AIAssistAdmin" `
        "admin_app.py"
}

$userExe = Join-Path $outputPath "AIAssistUser.exe"
$adminExe = Join-Path $outputPath "AIAssistAdmin.exe"

if (-not (Test-Path $userExe)) {
    throw "User executable not found: $userExe"
}
if (-not (Test-Path $adminExe)) {
    throw "Admin executable not found: $adminExe"
}

Write-Host "Desktop build completed."
Write-Host "- $userExe"
Write-Host "- $adminExe"
