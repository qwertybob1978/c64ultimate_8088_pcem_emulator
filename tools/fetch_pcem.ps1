$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$destination = Join-Path $root "third_party/pcem"
$revision = "d674c4088e04a5fdc74e452c4d5284fa8920726d"
$repository = "https://github.com/sarah-walker-pcem/pcem.git"

if (-not (Test-Path (Join-Path $destination ".git"))) {
    New-Item -ItemType Directory -Force -Path (Split-Path $destination) | Out-Null
    git clone --branch dev $repository $destination
}

git -c "safe.directory=$($destination.Replace('\', '/'))" -C $destination fetch origin dev
git -c "safe.directory=$($destination.Replace('\', '/'))" -C $destination checkout --detach $revision

$actual = git -c "safe.directory=$($destination.Replace('\', '/'))" -C $destination rev-parse HEAD
if ($actual -ne $revision) {
    throw "PCem revision mismatch: expected $revision, got $actual"
}

Write-Host "PCem reference is pinned at $actual"

