[CmdletBinding()]
param(
    [string]$PackageDir = (Join-Path $PSScriptRoot "..\artifacts\onedir\quiz-assistant"),
    [string]$OutputDir = (Join-Path $PSScriptRoot "..\artifacts\releases"),
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"

$packageRoot = (Resolve-Path -LiteralPath $PackageDir).Path
$executable = Join-Path $packageRoot "quiz-assistant.exe"
if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "Package is missing quiz-assistant.exe: $packageRoot"
}

$frontendCandidates = @(
    (Join-Path $packageRoot "frontend\dist\index.html"),
    (Join-Path $packageRoot "_internal\frontend\dist\index.html")
)
if (-not ($frontendCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf })) {
    throw "Package is missing bundled frontend/dist/index.html: $packageRoot"
}

if ([string]::IsNullOrWhiteSpace($Version)) {
    $pyproject = Join-Path $PSScriptRoot "..\pyproject.toml"
    $versionMatch = Select-String -LiteralPath $pyproject -Pattern '^\s*version\s*=\s*"([^"]+)"' | Select-Object -First 1
    if ($null -eq $versionMatch) {
        throw "Could not determine project version from pyproject.toml"
    }
    $Version = $versionMatch.Matches[0].Groups[1].Value
}

$outputRoot = [IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null
$releaseRoot = Join-Path $outputRoot ("QuizAssistant-{0}-windows-x64" -f $Version)
if (Test-Path -LiteralPath $releaseRoot) {
    throw "Release target already exists; choose another -OutputDir or remove it deliberately: $releaseRoot"
}

New-Item -ItemType Directory -Path $releaseRoot | Out-Null
Get-ChildItem -LiteralPath $packageRoot -Force | Copy-Item -Destination $releaseRoot -Recurse -Force

$manifestEntries = @(
    Get-ChildItem -LiteralPath $releaseRoot -Recurse -File |
        Sort-Object -Property FullName |
        ForEach-Object {
            $relative = $_.FullName.Substring($releaseRoot.Length).TrimStart('\').Replace('\', '/')
            [pscustomobject]@{
                path   = $relative
                bytes  = $_.Length
                sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
            }
        }
)

$manifest = [pscustomobject]@{
    format        = "quiz-assistant-release-manifest"
    version       = $Version
    platform      = "windows-x64"
    manifest_file = "release-manifest.json"
    created_at    = (Get-Date).ToUniversalTime().ToString("o")
    files         = $manifestEntries
}
$manifestPath = Join-Path $releaseRoot "release-manifest.json"
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

Write-Output ("Release created: {0}" -f $releaseRoot)
Write-Output ("Manifest files: {0}" -f $manifestEntries.Count)
