[CmdletBinding()]
param(
    [string]$PackageDir = (Join-Path $PSScriptRoot "..\artifacts\onedir\quiz-assistant"),
    [string]$OutputDir = (Join-Path $PSScriptRoot "..\artifacts\installer"),
    [string]$Version = "",
    [string]$Iscc = "iscc",
    [string]$CertificateThumbprint = "",
    [string]$TimestampServer = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$packageRoot = (Resolve-Path -LiteralPath $PackageDir).Path
$executable = Join-Path $packageRoot "quiz-assistant.exe"
if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "Package is missing quiz-assistant.exe: $packageRoot"
}

if ([string]::IsNullOrWhiteSpace($Version)) {
    $pyproject = Join-Path $projectRoot "pyproject.toml"
    $versionMatch = Select-String -LiteralPath $pyproject -Pattern '^\s*version\s*=\s*"([^"]+)"' | Select-Object -First 1
    if ($null -eq $versionMatch) {
        throw "Could not determine project version from pyproject.toml"
    }
    $Version = $versionMatch.Matches[0].Groups[1].Value
}

$isccCommand = Get-Command $Iscc -ErrorAction SilentlyContinue
if ($null -eq $isccCommand) {
    throw "Inno Setup compiler (ISCC.exe) was not found. Install Inno Setup before building the installer."
}
if (-not [string]::IsNullOrWhiteSpace($TimestampServer) -and
    [string]::IsNullOrWhiteSpace($CertificateThumbprint)) {
    throw "-TimestampServer requires -CertificateThumbprint"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$outputRoot = (Resolve-Path -LiteralPath $OutputDir).Path
$iss = Join-Path $PSScriptRoot "quiz-assistant.iss"
$arguments = @(
    ("/DAppVersion={0}" -f $Version),
    ("/DSourceDir={0}" -f $packageRoot),
    ("/O{0}" -f $outputRoot),
    $iss
)
& $isccCommand.Source @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compilation failed with exit code $LASTEXITCODE"
}

$installer = Join-Path $outputRoot ("QuizAssistant-{0}-setup.exe" -f $Version)
if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
    throw "Inno Setup completed but installer is missing: $installer"
}

if (-not [string]::IsNullOrWhiteSpace($CertificateThumbprint)) {
    $thumbprint = ($CertificateThumbprint -replace '\s', '').ToUpperInvariant()
    $certificate = Get-ChildItem -LiteralPath ("Cert:\CurrentUser\My\{0}" -f $thumbprint) -ErrorAction Stop
    $signatureParameters = @{ FilePath = $installer; Certificate = $certificate }
    if (-not [string]::IsNullOrWhiteSpace($TimestampServer)) {
        $signatureParameters.TimestampServer = $TimestampServer
    }
    $signature = Set-AuthenticodeSignature @signatureParameters
    if ($signature.Status -ne "Valid") {
        throw "Authenticode signing failed for installer: $($signature.Status)"
    }
}

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash.ToLowerInvariant()
$signatureStatus = (Get-AuthenticodeSignature -LiteralPath $installer).Status
[pscustomobject]@{
    Installer       = $installer
    SHA256          = $hash
    SignatureStatus = $signatureStatus
} | Format-List
