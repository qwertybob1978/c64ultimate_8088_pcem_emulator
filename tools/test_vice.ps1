param(
    [long]$CycleLimit = 8000000,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$manifest = Get-Content -Raw -LiteralPath (Join-Path $root "config/vice.json") | ConvertFrom-Json
$package = Join-Path $root (".cache/vice-" + $manifest.version + "/" + $manifest.packageDirectory)
$vice = Join-Path $package "bin/x64sc.exe"
$cartconv = Join-Path $package "bin/cartconv.exe"

if (-not (Test-Path -LiteralPath $vice) -or -not (Test-Path -LiteralPath $cartconv)) {
    & (Join-Path $PSScriptRoot "bootstrap_vice.ps1")
}

# VICE 3.10 exits before emulation if its per-user state directory does not
# already exist (common on clean CI/workstation images). Create only the
# narrow directory VICE needs; no machine-wide configuration is required.
$viceUserState = Join-Path ([Environment]::GetFolderPath("ApplicationData")) "vice"
New-Item -ItemType Directory -Force -Path $viceUserState | Out-Null

if (-not $SkipBuild) {
    & (Join-Path $root "build_crt.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "CRT build failed with exit code $LASTEXITCODE"
    }
}

$crt = (Resolve-Path (Join-Path $root "build/c64x86.crt")).Path
$build = (Resolve-Path (Join-Path $root "build")).Path
$screenshot = Join-Path $build "vice-smoke.png"
$log = Join-Path $build "vice-smoke.log"

& $cartconv --check $crt
if ($LASTEXITCODE -ne 0) {
    throw "VICE cartconv rejected $crt"
}

Remove-Item -LiteralPath $screenshot, $log -Force -ErrorAction SilentlyContinue
$arguments = @(
    "-default",
    "+confirmonexit",
    "+sound",
    "-warp",
    "-reu",
    "-reusize", "16384",
    "-cartcrt", ('"' + $crt + '"'),
    "-limitcycles", $CycleLimit,
    "-exitscreenshot", ('"' + $screenshot + '"'),
    "-logfile", ('"' + $log + '"')
)

$process = Start-Process `
    -FilePath $vice `
    -ArgumentList $arguments `
    -WorkingDirectory (Split-Path $vice) `
    -WindowStyle Normal `
    -PassThru

# VICE 3.10 on Windows logs the cycle-limit event but can leave its GTK
# window open instead of terminating. Poll the shared log, then close the
# window normally so -exitscreenshot is written and no stale VICE remains.
$deadline = (Get-Date).AddMinutes(10)
$cycleLimitReached = $false
while (-not $process.HasExited -and (Get-Date) -lt $deadline) {
    if (Test-Path -LiteralPath $log) {
        try {
            $stream = [System.IO.File]::Open(
                $log,
                [System.IO.FileMode]::Open,
                [System.IO.FileAccess]::Read,
                [System.IO.FileShare]::ReadWrite
            )
            $reader = [System.IO.StreamReader]::new($stream)
            try {
                $cycleLimitReached = $reader.ReadToEnd() -match "cycle limit reached"
            } finally {
                $reader.Dispose()
                $stream.Dispose()
            }
        } catch [System.IO.IOException] {
            # The GTK logger may briefly hold the file exclusively at startup.
        }
    }
    if ($cycleLimitReached) {
        [void]$process.CloseMainWindow()
        break
    }
    Start-Sleep -Milliseconds 250
    $process.Refresh()
}

if (-not $process.WaitForExit(5000)) {
    Stop-Process -Id $process.Id -Force
    if (-not $cycleLimitReached) {
        throw "VICE did not reach the $CycleLimit-cycle limit within ten minutes"
    }
}
$process.Refresh()

# VICE intentionally uses status 1 for some cycle-limit exits.
if ($process.ExitCode -notin @(0, 1)) {
    throw "VICE exited unexpectedly with code $($process.ExitCode)"
}
if (-not (Test-Path -LiteralPath $screenshot) -or -not (Test-Path -LiteralPath $log)) {
    throw "VICE did not create the smoke-test screenshot and log"
}

$logText = Get-Content -Raw -LiteralPath $log
foreach ($expected in @("VICE Version $($manifest.version)", "REUsize=16384", "REU=1", "cycle limit reached")) {
    if ($logText -notmatch [regex]::Escape($expected)) {
        throw "VICE log does not confirm '$expected'"
    }
}

Add-Type -AssemblyName System.Drawing
$bitmap = [System.Drawing.Bitmap]::FromFile($screenshot)
try {
    $border = $bitmap.GetPixel(0, 0)
} finally {
    $bitmap.Dispose()
}
if ($border.G -le ($border.R + 15) -or $border.G -le ($border.B + 15)) {
    throw "Diagnostic did not finish with a green pass border (RGB $($border.R),$($border.G),$($border.B)); inspect $screenshot"
}

Write-Host "VICE $($manifest.version) CRT smoke test passed with a 16 MiB REU."
Write-Host "Screenshot: $screenshot"
Write-Host "Log: $log"
