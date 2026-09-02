[CmdletBinding()]
param(
    [switch]$RequireChinese
)

$ErrorActionPreference = "Stop"

$candidates = @(
    $env:TESSERACT_CMD,
    "C:\Program Files\Tesseract-OCR\tesseract.exe",
    "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    (Join-Path $env:LOCALAPPDATA "Programs\Tesseract-OCR\tesseract.exe")
) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }

$tesseract = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $tesseract) {
    $command = Get-Command tesseract -ErrorAction SilentlyContinue
    if ($command) {
        $tesseract = $command.Source
    }
}
if (-not $tesseract) {
    throw "Tesseract was not found. Install it or set TESSERACT_CMD to tesseract.exe."
}

$version = (& $tesseract --version 2>&1 | Select-Object -First 1)
$languages = @(& $tesseract --list-langs 2>$null)
$languageNames = @($languages | Select-Object -Skip 1 | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if ($RequireChinese -and "chi_sim" -notin $languageNames) {
    throw "Tesseract was found but chi_sim.traineddata is missing: $tesseract"
}

[pscustomobject]@{
    Executable = $tesseract
    Version = $version
    Languages = ($languageNames -join ", ")
    ChineseReady = ("chi_sim" -in $languageNames)
} | Format-List
