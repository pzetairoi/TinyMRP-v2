param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$DeliverablesDir,

  [Parameter(Mandatory = $false)]
  [int]$HttpPort = 5000
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot() {
  $scriptDir = Split-Path -Parent $PSCommandPath
  return (Resolve-Path (Join-Path $scriptDir "..")).Path
}

function Normalize-DockerPath([string]$Path) {
  $full = [System.IO.Path]::GetFullPath($Path)
  return ($full -replace "\\", "/")
}

Write-Host "TinyMRP one-folder container setup"

$repoRoot = Get-RepoRoot
Push-Location $repoRoot
try {
$deliverablesFull = [System.IO.Path]::GetFullPath($DeliverablesDir)
$mongoDir = Join-Path $deliverablesFull ".tinymrp\\mongo"
$instanceDir = Join-Path $deliverablesFull ".tinymrp\\instance"
$envFile = Join-Path $deliverablesFull ".tinymrp\\compose.env"
$composeFile = Join-Path $repoRoot "docker-compose.onefolder.yml"

New-Item -ItemType Directory -Force -Path $deliverablesFull | Out-Null
New-Item -ItemType Directory -Force -Path $mongoDir | Out-Null
New-Item -ItemType Directory -Force -Path $instanceDir | Out-Null

$dockerDeliverables = Normalize-DockerPath $deliverablesFull

# Persist compose settings under the deliverables folder so follow-up commands
# (logs/down/ps) work even in a fresh shell without re-exporting env vars.
@(
  "TINYMRP_DELIVERABLES_DIR=$dockerDeliverables"
  "HTTP_PORT=$HttpPort"
) | Set-Content -Encoding ascii -NoNewline:$false -Path $envFile

$env:TINYMRP_DELIVERABLES_DIR = $dockerDeliverables
$env:HTTP_PORT = "$HttpPort"

Write-Host "Using deliverables folder:" $deliverablesFull
Write-Host "Starting containers on http://localhost:$HttpPort/ ..."

docker compose --env-file $envFile -f $composeFile up -d --build

Write-Host ""
Write-Host "Container is starting. Get the generated admin password with:"
Write-Host "  docker compose --env-file `"$envFile`" -f `"$composeFile`" logs -n 200 app"
Write-Host ""
Write-Host "Look for: Generated one-time admin password:"
Write-Host "Default admin email is: admin@example.com (override with TINYMRP_ADMIN_EMAIL if desired)"
Write-Host ""
Write-Host "To stop:"
Write-Host "  docker compose --env-file `"$envFile`" -f `"$composeFile`" down"
} finally {
  Pop-Location
}
