param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$cache = Join-Path $root ".cache"
$install = Join-Path $cache "cc65"
$archive = Join-Path $cache "cc65-snapshot-win64.zip"
$assembler = Join-Path $install "bin/ca65.exe"
$linker = Join-Path $install "bin/ld65.exe"
$url = "https://downloads.sourceforge.net/project/cc65/cc65-snapshot-win64.zip"

if (-not $Force -and (Test-Path $assembler) -and (Test-Path $linker)) {
    Write-Host "Project-local cc65 is already installed:"
    & $assembler --version
    & $linker --version
    exit 0
}

New-Item -ItemType Directory -Force -Path $cache | Out-Null
Write-Host "Downloading the official cc65 Windows snapshot..."
& curl.exe -L --fail --output $archive $url
if ($LASTEXITCODE -ne 0) {
    throw "cc65 download failed with exit code $LASTEXITCODE"
}

$stream = [System.IO.File]::OpenRead($archive)
try {
    $signature = New-Object byte[] 4
    if ($stream.Read($signature, 0, 4) -ne 4 -or
        $signature[0] -ne 0x50 -or $signature[1] -ne 0x4B -or
        $signature[2] -ne 0x03 -or $signature[3] -ne 0x04) {
        throw "Downloaded cc65 file is not a ZIP archive"
    }
} finally {
    $stream.Dispose()
}

New-Item -ItemType Directory -Force -Path $install | Out-Null
Expand-Archive -LiteralPath $archive -DestinationPath $install -Force

if (-not (Test-Path $assembler) -or -not (Test-Path $linker)) {
    throw "cc65 archive did not contain bin/ca65.exe and bin/ld65.exe"
}

Write-Host "Installed project-local cc65:"
& $assembler --version
& $linker --version

