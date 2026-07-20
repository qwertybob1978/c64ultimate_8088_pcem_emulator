$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root ".cache/python"
New-Item -ItemType Directory -Force -Path $target | Out-Null

python -m pip install `
    --disable-pip-version-check `
    --target $target `
    --requirement (Join-Path $root "requirements-test.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Python test dependency installation failed with exit code $LASTEXITCODE"
}

Write-Host "Python test dependencies ready: $target"
