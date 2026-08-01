$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "build.ps1")
if ($LASTEXITCODE -ne 0) { throw "payload build failed with exit code $LASTEXITCODE" }

$build = Join-Path $PSScriptRoot "build"
$svardosImage = Join-Path $PSScriptRoot "third_party/svardos/svdos-360K-disk-1.img"
if (Test-Path $svardosImage) {
    $diskImage = Get-Item $svardosImage
} else {
    $diskImage = Get-ChildItem (Join-Path $PSScriptRoot ".cache/media/msdos330") -Recurse -Filter DISK01.IMG -ErrorAction SilentlyContinue | Select-Object -First 1
}
$portableToolchain = Join-Path $PSScriptRoot ".cache/cc65/bin"
$assembler = Get-Command ca65 -ErrorAction SilentlyContinue
$linker = Get-Command ld65 -ErrorAction SilentlyContinue
if (-not $assembler) { $assembler = Get-Item (Join-Path $portableToolchain "ca65.exe") }
if (-not $linker) { $linker = Get-Item (Join-Path $portableToolchain "ld65.exe") }
$assemblerPath = if ($assembler.Source) { $assembler.Source } else { $assembler.FullName }
$linkerPath = if ($linker.Source) { $linker.Source } else { $linker.FullName }

$generateArgs = @((Join-Path $PSScriptRoot "tools/generate_cartridge_include.py"))
if ($diskImage) { $generateArgs += @("--media", $diskImage.FullName) }
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
if ($diskImage) { $buildArgs += @("--media", $diskImage.FullName) }
python @buildArgs
if ($LASTEXITCODE -ne 0) { throw "CRT packaging failed" }
python (Join-Path $PSScriptRoot "tools/build_crt.py") --check (Join-Path $build "c64x86.crt")
if ($LASTEXITCODE -ne 0) { throw "CRT validation failed" }
