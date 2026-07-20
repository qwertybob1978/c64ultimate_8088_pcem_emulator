$ErrorActionPreference = "Stop"

$build = Join-Path $PSScriptRoot "build"
$portableToolchain = Join-Path $PSScriptRoot ".cache/cc65/bin"

$assembler = Get-Command ca65 -ErrorAction SilentlyContinue
$linker = Get-Command ld65 -ErrorAction SilentlyContinue
if (-not $assembler -and (Test-Path (Join-Path $portableToolchain "ca65.exe"))) {
    $assembler = Get-Item (Join-Path $portableToolchain "ca65.exe")
}
if (-not $linker -and (Test-Path (Join-Path $portableToolchain "ld65.exe"))) {
    $linker = Get-Item (Join-Path $portableToolchain "ld65.exe")
}
if (-not $assembler -or -not $linker) {
    throw "ca65 and ld65 were not found; install cc65 or unpack it under .cache/cc65"
}
$assemblerPath = if ($assembler.Source) { $assembler.Source } else { $assembler.FullName }
$linkerPath = if ($linker.Source) { $linker.Source } else { $linker.FullName }

python (Join-Path $PSScriptRoot "tools/generate_cpu8088.py") --check
if ($LASTEXITCODE -ne 0) {
    throw "generated 8088 CPU contracts are stale"
}

$objects = @(
    @{ Source = "src/boot/hwtest.s"; Object = "boot/hwtest.o" },
    @{ Source = "src/host/turbo.s"; Object = "host/turbo.o" },
    @{ Source = "src/memory/reu.s"; Object = "memory/reu.o" },
    @{ Source = "src/memory/page_cache.s"; Object = "memory/page_cache.o" },
    @{ Source = "src/cpu8088/state.s"; Object = "cpu8088/state.o" },
    @{ Source = "src/cpu8088/address.s"; Object = "cpu8088/address.o" },
    @{ Source = "src/cpu8088/step.s"; Object = "cpu8088/step.o" }
)

New-Item -ItemType Directory -Force -Path $build | Out-Null

foreach ($unit in $objects) {
    $source = Join-Path $PSScriptRoot $unit.Source
    $object = Join-Path $build $unit.Object
    New-Item -ItemType Directory -Force -Path (Split-Path $object) | Out-Null
    & $assemblerPath -I (Join-Path $PSScriptRoot "src") -g -o $object $source
    if ($LASTEXITCODE -ne 0) {
        throw "ca65 failed for $($unit.Source) with exit code $LASTEXITCODE"
    }
}

$objectPaths = $objects | ForEach-Object { Join-Path $build $_.Object }
& $linkerPath `
    -C (Join-Path $PSScriptRoot "cfg/c64x86.cfg") `
    -m (Join-Path $build "c64x86-hwtest.map") `
    -Ln (Join-Path $build "c64x86-hwtest.lbl") `
    -o (Join-Path $build "c64x86-hwtest.prg") `
    @objectPaths
if ($LASTEXITCODE -ne 0) {
    throw "ld65 failed with exit code $LASTEXITCODE"
}

Write-Host "Built build/c64x86-hwtest.prg"
