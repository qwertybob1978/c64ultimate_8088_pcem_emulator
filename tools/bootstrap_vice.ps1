$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $root "config/vice.json"
$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
$cache = Join-Path $root ".cache"
$archive = Join-Path $cache $manifest.archive
$install = Join-Path $cache ("vice-" + $manifest.version)
$package = Join-Path $install $manifest.packageDirectory
$vice = Join-Path $package "bin/x64sc.exe"
$cartconv = Join-Path $package "bin/cartconv.exe"

New-Item -ItemType Directory -Force -Path $cache | Out-Null

if (-not (Test-Path -LiteralPath $archive)) {
    Write-Host "Downloading VICE $($manifest.version) from the official release archive..."
    & curl.exe -L --fail --output $archive $manifest.url
    if ($LASTEXITCODE -ne 0) {
        throw "VICE download failed with exit code $LASTEXITCODE"
    }
}

$actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()
if ($actualHash -ne $manifest.sha256) {
    throw "VICE archive checksum mismatch: expected $($manifest.sha256), got $actualHash"
}

if (-not (Test-Path -LiteralPath $vice) -or -not (Test-Path -LiteralPath $cartconv)) {
    Write-Host "Extracting VICE into the project-local cache..."
    Expand-Archive -LiteralPath $archive -DestinationPath $install -Force
}

if (-not (Test-Path -LiteralPath $vice) -or -not (Test-Path -LiteralPath $cartconv)) {
    throw "VICE package does not contain the expected x64sc.exe and cartconv.exe"
}

Write-Host "VICE $($manifest.version) ready: $vice"
Write-Host "cartconv ready: $cartconv"
