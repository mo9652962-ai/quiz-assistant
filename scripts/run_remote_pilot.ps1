param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

if (-not $env:QUIZ_REMOTE_ENABLED) {
    $env:QUIZ_REMOTE_ENABLED = "true"
}
if (-not $env:QUIZ_REMOTE_READ_ONLY) {
    $env:QUIZ_REMOTE_READ_ONLY = "true"
}
if (-not $env:QUIZ_REMOTE_HOST) {
    $env:QUIZ_REMOTE_HOST = "127.0.0.1"
}
if (-not $env:QUIZ_REMOTE_PORT) {
    $env:QUIZ_REMOTE_PORT = "8765"
}

$env:PYTHONPATH = "src"
& $Python -m uvicorn quiz_assistant.server:app --host $env:QUIZ_REMOTE_HOST --port ([int]$env:QUIZ_REMOTE_PORT)
exit $LASTEXITCODE
