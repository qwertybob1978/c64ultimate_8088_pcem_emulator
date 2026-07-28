param(
    [long]$CycleLimit = 2000000000,
    [int]$DelaySeconds = 2,
    [switch]$RebuildEachRun,
    [switch]$Once
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$testScript = Join-Path $PSScriptRoot "test_vice.ps1"
$buildScript = Join-Path $root "build_crt.ps1"
$buildDir = Join-Path $root "build"
$archiveDir = Join-Path $buildDir "long-runs"

if ($CycleLimit -le 0) {
    throw "CycleLimit must be positive"
}
if ($DelaySeconds -lt 0) {
    throw "DelaySeconds cannot be negative"
}

Set-Location $root
New-Item -ItemType Directory -Force -Path $archiveDir | Out-Null

Write-Host "C64 x86 long-run harness"
Write-Host "Root: $root"
Write-Host "Cycle limit: $CycleLimit"
Write-Host "Archive: $archiveDir"
Write-Host "Press Ctrl+C to stop."

$run = 0
$skipBuild = $false

try {
    do {
        $run++
        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $runName = "run-{0:D5}-{1}" -f $run, $stamp
        $runArchive = Join-Path $archiveDir $runName
        New-Item -ItemType Directory -Force -Path $runArchive | Out-Null

        Write-Host "[$stamp] Starting run $run"
        try {
            if (-not $skipBuild -or $RebuildEachRun) {
                & $buildScript
                if ($LASTEXITCODE -ne 0) {
                    throw "CRT build failed with exit code $LASTEXITCODE"
                }
                $skipBuild = $true
            }

            $args = @("-CycleLimit", $CycleLimit)
            if ($skipBuild -and -not $RebuildEachRun) {
                $args += "-SkipBuild"
            }
            & $testScript @args
            if ($LASTEXITCODE -ne 0) {
                throw "VICE gate failed with exit code $LASTEXITCODE"
            }
            $skipBuild = $true
            Write-Host "[$stamp] Run $run passed"
        } catch {
            Write-Warning "[$stamp] Run $run failed: $($_.Exception.Message)"
        } finally {
            foreach ($artifact in @("vice-smoke.log", "vice-smoke.png")) {
                $source = Join-Path $buildDir $artifact
                if (Test-Path -LiteralPath $source) {
                    Copy-Item -LiteralPath $source -Destination (Join-Path $runArchive $artifact) -Force
                }
            }
            $status = [ordered]@{
                run = $run
                started = $stamp
                cycleLimit = $CycleLimit
                archived = (Get-ChildItem -LiteralPath $runArchive -File | Select-Object -ExpandProperty Name)
            }
            $status | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runArchive "status.json")
        }

        if (-not $Once -and $DelaySeconds -gt 0) {
            Start-Sleep -Seconds $DelaySeconds
        }
    } while (-not $Once)
} finally {
    Write-Host "Long-run harness stopped after $run run(s)."
}
