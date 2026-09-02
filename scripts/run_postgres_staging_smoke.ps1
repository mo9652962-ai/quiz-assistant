[CmdletBinding()]
param(
    [string]$SnapshotPath = (Join-Path $PSScriptRoot "..\work\migration.snapshot.json"),
    [switch]$ImportSnapshot,
    [switch]$ConfirmStagingWrite,
    [string]$Uv = (Join-Path $PSScriptRoot "..\.venv\Scripts\uv.exe")
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($env:QUIZ_DATABASE_URL)) {
    throw "Set QUIZ_DATABASE_URL to the dedicated PostgreSQL staging database before running this script."
}
try {
    $databaseUri = [Uri]$env:QUIZ_DATABASE_URL
} catch {
    throw "QUIZ_DATABASE_URL is not a valid database URL"
}
if ($databaseUri.Scheme -notin @("postgres", "postgresql")) {
    throw "This script only accepts a PostgreSQL QUIZ_DATABASE_URL"
}
if (-not $ConfirmStagingWrite) {
    throw "Pass -ConfirmStagingWrite to acknowledge that migration/import writes to staging"
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$uvPath = $Uv
if (-not [IO.Path]::IsPathRooted($uvPath)) {
    $uvCommand = Get-Command $uvPath -ErrorAction SilentlyContinue
    if ($null -eq $uvCommand) {
        throw "uv was not found: $uvPath"
    }
    $uvPath = $uvCommand.Source
}
if (-not (Test-Path -LiteralPath $uvPath -PathType Leaf)) {
    throw "uv executable not found: $uvPath"
}

$env:PYTHONPATH = Join-Path $projectRoot "src"
$migrationArgs = @("run", "--locked", "--extra", "remote", "quiz", "postgres-migrate")
& $uvPath @migrationArgs
if ($LASTEXITCODE -ne 0) {
    throw "PostgreSQL staging migration failed with exit code $LASTEXITCODE"
}

if ($ImportSnapshot) {
    $snapshot = (Resolve-Path -LiteralPath $SnapshotPath).Path
    $importArgs = @(
        "run", "--locked", "--extra", "remote", "quiz", "postgres-import-snapshot",
        "--source", $snapshot
    )
    & $uvPath @importArgs
    if ($LASTEXITCODE -ne 0) {
        throw "PostgreSQL staging snapshot import failed with exit code $LASTEXITCODE"
    }
}

Write-Output "PostgreSQL staging migration completed."
if ($ImportSnapshot) {
    Write-Output "PostgreSQL staging snapshot import completed."
}
