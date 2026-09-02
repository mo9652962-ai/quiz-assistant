[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ReleaseDir
)

$ErrorActionPreference = "Stop"

$releaseRoot = (Resolve-Path -LiteralPath $ReleaseDir).Path
$manifestPath = Join-Path $releaseRoot "release-manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "Release is missing release-manifest.json: $releaseRoot"
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.format -ne "quiz-assistant-release-manifest") {
    throw "Unsupported release manifest format"
}
if ($manifest.manifest_file -ne "release-manifest.json") {
    throw "Manifest must identify release-manifest.json as its excluded self-file"
}

$expected = @{}
foreach ($entry in @($manifest.files)) {
    $relative = [string]$entry.path
    $windowsRelative = $relative.Replace('/', '\')
    if ([string]::IsNullOrWhiteSpace($relative) -or
        [IO.Path]::IsPathRooted($windowsRelative) -or
        ($windowsRelative -split '\\' | Where-Object { $_ -eq '..' })) {
        throw "Unsafe manifest path: $relative"
    }
    if ($expected.ContainsKey($relative)) {
        throw "Duplicate manifest path: $relative"
    }
    $expected[$relative] = $entry
}

$actual = @{}
foreach ($file in @(Get-ChildItem -LiteralPath $releaseRoot -Recurse -File)) {
    $relative = $file.FullName.Substring($releaseRoot.Length).TrimStart('\').Replace('\', '/')
    if ($relative -eq "release-manifest.json") {
        continue
    }
    $actual[$relative] = $file
}

$unexpected = @($actual.Keys | Where-Object { -not $expected.ContainsKey($_) })
$missing = @($expected.Keys | Where-Object { -not $actual.ContainsKey($_) })
if ($unexpected.Count -gt 0) {
    throw ("Unexpected release files: {0}" -f ($unexpected -join ", "))
}
if ($missing.Count -gt 0) {
    throw ("Missing release files: {0}" -f ($missing -join ", "))
}

foreach ($relative in $expected.Keys) {
    $file = $actual[$relative]
    $entry = $expected[$relative]
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
    if ([int64]$entry.bytes -ne $file.Length -or [string]$entry.sha256.ToLowerInvariant() -ne $hash) {
        throw "SHA-256 or byte-count mismatch: $relative"
    }
}

Write-Output ("Release verified: {0}" -f $releaseRoot)
Write-Output ("Manifest files verified: {0}" -f $expected.Count)
