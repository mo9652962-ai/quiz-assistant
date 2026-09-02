[CmdletBinding()]
param(
    [string]$OutputDir = (Join-Path $PSScriptRoot "..\artifacts\onedir"),
    [string]$WorkDir = (Join-Path $PSScriptRoot "..\artifacts\pyinstaller-work")
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

if (-not (Test-Path "frontend\dist\index.html")) {
    Push-Location frontend
    npm run build
    Pop-Location
}

$pyinstaller = Join-Path $projectRoot ".venv\Scripts\pyinstaller.exe"
if (-not (Test-Path $pyinstaller)) {
    throw "PyInstaller not found. Run: .venv\Scripts\python.exe -m pip install -e .[package]"
}

$runningPackage = Get-Process -Name "quiz-assistant" -ErrorAction SilentlyContinue
if ($runningPackage) {
    throw "A previous quiz-assistant.exe is still running. Stop it before rebuilding so Windows can release package DLLs."
}

# The spec's COLLECT() defines the onedir layout; PyInstaller rejects --onedir
# and --specpath when a .spec file is supplied.
& $pyinstaller --noconfirm --clean "packaging\quiz.spec" `
    --distpath $OutputDir --workpath $WorkDir
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$executable = Join-Path $OutputDir "quiz-assistant\quiz-assistant.exe"
if (-not (Test-Path $executable)) {
    throw "Package was built but executable is missing: $executable"
}
Write-Host "Built: $executable"
