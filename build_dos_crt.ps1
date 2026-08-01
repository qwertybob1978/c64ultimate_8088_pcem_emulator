param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$DiskImage
)

$ErrorActionPreference = "Stop"

$buildCrt = Join-Path $PSScriptRoot "build_crt.ps1"
$arguments = @{ DiskImage = $DiskImage }

& $buildCrt @arguments
if ($LASTEXITCODE -ne 0) {
    throw "CRT build failed with exit code $LASTEXITCODE"
}

Write-Host "CRT ready: $PSScriptRoot\build\c64x86.crt"
Write-Host "DOS media: $DiskImage"