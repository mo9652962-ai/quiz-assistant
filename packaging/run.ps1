[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $PSScriptRoot "..\artifacts\onedir\quiz-assistant"),
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"
$installRoot = (Resolve-Path $InstallDir).Path
$executable = Join-Path $installRoot "quiz-assistant.exe"
if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "quiz-assistant.exe not found under $installRoot. Build the package first."
}
$frontendCandidates = @(
    (Join-Path $installRoot "frontend\dist"),
    (Join-Path $installRoot "_internal\frontend\dist")
)
$frontendRoot = $frontendCandidates |
    Where-Object { Test-Path -LiteralPath (Join-Path $_ "index.html") -PathType Leaf } |
    Select-Object -First 1
if (-not $frontendRoot) {
    throw "Bundled frontend/dist/index.html not found under $installRoot. Build the frontend first."
}

$dataRoot = Join-Path $env:LOCALAPPDATA "QuizAssistant"
$dataDir = Join-Path $dataRoot "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $dataDir "backups") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $dataDir "exports") | Out-Null

$existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    throw "Port $Port is already in use. Stop the owning process or choose another -Port; the launcher will not bind to 0.0.0.0."
}

$env:QUIZ_DB_PATH = Join-Path $dataDir "quiz.db"
$env:QUIZ_FRONTEND_DIST = $frontendRoot
$env:QUIZ_REMOTE_HOST = "127.0.0.1"
$env:QUIZ_REMOTE_PORT = [string]$Port
$env:QUIZ_REMOTE_ENABLED = "false"
$env:QUIZ_AI_ENABLED = "false"
if (-not $env:QUIZ_LOCAL_SESSION_TOKEN) {
    $env:QUIZ_LOCAL_SESSION_TOKEN = [guid]::NewGuid().ToString("N")
}

Write-Host "Quiz Assistant: http://127.0.0.1:$Port"
Write-Host "Data directory: $dataDir"
Write-Host "Local session token: $env:QUIZ_LOCAL_SESSION_TOKEN"
& $executable
