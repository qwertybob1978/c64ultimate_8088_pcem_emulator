param(
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$manifest = Get-Content -Raw -LiteralPath (Join-Path $root "config/vice.json") | ConvertFrom-Json
$package = Join-Path $root (".cache/vice-" + $manifest.version + "/" + $manifest.packageDirectory)
$vice = Join-Path $package "bin/x64sc.exe"

if (-not (Test-Path -LiteralPath $vice)) {
    & (Join-Path $root "tools/bootstrap_vice.ps1")
}

if (-not $SkipBuild) {
    & (Join-Path $root "build_crt.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "CRT build failed with exit code $LASTEXITCODE"
    }
}

$crt = (Resolve-Path (Join-Path $root "build/c64x86.crt")).Path
$arguments = @(
    "-default",
    "+confirmonexit",
    "+sound",
    "-warp",
    "-reu",
    "-reusize", "16384",
    "-cartcrt", ('"' + $crt + '"')
)

$process = Start-Process `
    -FilePath $vice `
    -ArgumentList $arguments `
    -WorkingDirectory (Split-Path $vice) `
    -WindowStyle Normal `
    -PassThru

Write-Host "Started VICE $($manifest.version) in warp mode with the latest CRT."
Write-Host "PID: $($process.Id)"
Write-Host "CRT: $crt"
