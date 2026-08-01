param(
    [string]$DiskImage = "third_party/svardos/svdos-360K-disk-1.img"
)

$ErrorActionPreference = "Stop"

$build = Join-Path $PSScriptRoot "build"
$diskImagePath = if ([IO.Path]::IsPathRooted($DiskImage)) {
    $DiskImage
}
else {
    Join-Path $PSScriptRoot $DiskImage
}
if (-not (Test-Path -LiteralPath $diskImagePath -PathType Leaf)) {
    throw "required disk image not found: $diskImagePath"
}
$diskImageInfo = Get-Item -LiteralPath $diskImagePath
$diskImagePath = $diskImageInfo.FullName
$geometry = switch ([int64]$diskImageInfo.Length) {
    163840 { @{ SectorsPerTrack = 8; HeadsPerCylinder = 1 }; break }
    327680 { @{ SectorsPerTrack = 8; HeadsPerCylinder = 2 }; break }
    368640 { @{ SectorsPerTrack = 9; HeadsPerCylinder = 2 }; break }
    default { $null }
}
if (-not $geometry) {
    throw "DOS disk image must be exactly 160 KiB, 320 KiB, or 360 KiB; got $($diskImageInfo.Length) bytes: $diskImagePath"
}
@(
    "SECTORS_PER_TRACK = $($geometry.SectorsPerTrack)"
    "HEADS_PER_CYLINDER = $($geometry.HeadsPerCylinder)"
) | Set-Content -LiteralPath (Join-Path $build "media_geometry.inc") -Encoding ascii
Write-Host "DOS media: $diskImagePath ($($diskImageInfo.Length) bytes)"
Write-Host "Geometry: $($geometry.HeadsPerCylinder) head(s), $($geometry.SectorsPerTrack) sectors/track"

& (Join-Path $PSScriptRoot "build.ps1")
if ($LASTEXITCODE -ne 0) { throw "payload build failed with exit code $LASTEXITCODE" }

$portableToolchain = Join-Path $PSScriptRoot ".cache/cc65/bin"
$assembler = Get-Command ca65 -ErrorAction SilentlyContinue
$linker = Get-Command ld65 -ErrorAction SilentlyContinue
if (-not $assembler) { $assembler = Get-Item (Join-Path $portableToolchain "ca65.exe") }
if (-not $linker) { $linker = Get-Item (Join-Path $portableToolchain "ld65.exe") }
$assemblerPath = if ($assembler.Source) { $assembler.Source } else { $assembler.FullName }
$linkerPath = if ($linker.Source) { $linker.Source } else { $linker.FullName }

$generateArgs = @((Join-Path $PSScriptRoot "tools/generate_cartridge_include.py"))
$generateArgs += @("--media", $diskImagePath)
python @generateArgs
if ($LASTEXITCODE -ne 0) { throw "cartridge include generation failed" }

$bootstrapObject = Join-Path $build "cartridge-bootstrap.o"
& $assemblerPath `
    -I (Join-Path $PSScriptRoot "src") `
    -I $build `
    -g `
    -o $bootstrapObject `
(Join-Path $PSScriptRoot "src/cartridge/bootstrap.s")
if ($LASTEXITCODE -ne 0) { throw "cartridge bootstrap assembly failed" }

& $linkerPath `
    -C (Join-Path $PSScriptRoot "cfg/cartridge_bootstrap.cfg") `
    -o (Join-Path $build "cartridge-bootstrap.bin") `
    $bootstrapObject
if ($LASTEXITCODE -ne 0) { throw "cartridge bootstrap link failed" }

$buildArgs = @((Join-Path $PSScriptRoot "tools/build_crt.py"))
$buildArgs += @("--media", $diskImagePath)
python @buildArgs
if ($LASTEXITCODE -ne 0) { throw "CRT packaging failed" }
python (Join-Path $PSScriptRoot "tools/build_crt.py") --check (Join-Path $build "c64x86.crt")
if ($LASTEXITCODE -ne 0) { throw "CRT validation failed" }
