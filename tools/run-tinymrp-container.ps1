param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$DeliverablesDir,

  [Parameter(Mandatory = $false)]
  [int]$HttpPort = 5000,

  [Parameter(Mandatory = $false)]
  [string]$AdminEmail = "admin@example.com"
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

function Get-EnvFileValue([string]$Path, [string]$Name) {
  if (-not (Test-Path -LiteralPath $Path)) {
    return $null
  }
  $prefix = "$Name="
  foreach ($line in Get-Content -LiteralPath $Path) {
    if ($line.StartsWith($prefix)) {
      return $line.Substring($prefix.Length)
    }
  }
  return $null
}

function New-SecureRandomHex([int]$ByteCount = 24) {
  $bytes = New-Object byte[] $ByteCount
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try {
    $rng.GetBytes($bytes)
  } finally {
    $rng.Dispose()
  }
  return ([System.BitConverter]::ToString($bytes) -replace "-", "").ToLowerInvariant()
}

Write-Host "TinyMRP one-folder container setup"

$repoRoot = Get-RepoRoot
Push-Location $repoRoot
try {
  $deliverablesFull = [System.IO.Path]::GetFullPath($DeliverablesDir)
  $mongoDir = Join-Path $deliverablesFull ".tinymrp\mongo"
  $instanceDir = Join-Path $deliverablesFull ".tinymrp\instance"
  $envFile = Join-Path $deliverablesFull ".tinymrp\compose.env"
  $composeFile = Join-Path $repoRoot "docker-compose.onefolder.yml"

  New-Item -ItemType Directory -Force -Path $deliverablesFull | Out-Null
  New-Item -ItemType Directory -Force -Path $mongoDir | Out-Null
  New-Item -ItemType Directory -Force -Path $instanceDir | Out-Null

  $dockerDeliverables = Normalize-DockerPath $deliverablesFull
  $existingConfiguration = Test-Path -LiteralPath $envFile
  $mongoHasData = Get-ChildItem -LiteralPath $mongoDir -Force | Select-Object -First 1
  if ($mongoHasData) {
    $existingConfiguration = $true
  }
  $existingAdminEmail = Get-EnvFileValue $envFile "TINYMRP_ADMIN_EMAIL"
  $existingAdminPassword = Get-EnvFileValue $envFile "TINYMRP_ADMIN_PASSWORD"
  $generatedAdminPassword = $false
  $legacyConfigurationWithoutPassword = $false
  $bootstrapEnabled = "true"

  if ($existingAdminEmail) {
    $AdminEmail = $existingAdminEmail
  }
  if ($existingAdminPassword) {
    $adminPassword = $existingAdminPassword
  } elseif ($existingConfiguration) {
    # Older helper versions intentionally did not persist the generated
    # password. Never invent and display a replacement that bootstrap will not
    # apply to an existing user database.
    $adminPassword = ""
    $bootstrapEnabled = "false"
    $legacyConfigurationWithoutPassword = $true
  } else {
    $adminPassword = New-SecureRandomHex
    $generatedAdminPassword = $true
  }
  try {
    $parsedAdminEmail = New-Object System.Net.Mail.MailAddress($AdminEmail)
  } catch {
    throw "AdminEmail must be a valid email address."
  }
  if ($parsedAdminEmail.Address -ne $AdminEmail) {
    throw "AdminEmail must contain only a plain email address."
  }

  # Persist settings so follow-up compose commands and restarts use the same
  # credentials. Bootstrap never resets an existing user's password.
  @(
    "TINYMRP_DELIVERABLES_DIR=$dockerDeliverables"
    "HTTP_PORT=$HttpPort"
    "TINYMRP_SECURITY_MODE=compat"
    "TINYMRP_SEED_ADMIN=$bootstrapEnabled"
    "TINYMRP_ADMIN_EMAIL=$AdminEmail"
    "TINYMRP_ADMIN_PASSWORD=$adminPassword"
  ) | Set-Content -Encoding ascii -NoNewline:$false -Path $envFile

  Write-Host "Using deliverables folder:" $deliverablesFull
  Write-Host "Starting containers on http://localhost:$HttpPort/ ..."

  docker compose --env-file $envFile -f $composeFile up -d --build
  if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed with exit code $LASTEXITCODE."
  }

  Write-Host ""
  if ($generatedAdminPassword) {
    Write-Host "First administrator credentials (shown once; also stored in the compose env file):"
    Write-Host "  Email:    $AdminEmail"
    Write-Host "  Password: $adminPassword"
  } elseif ($legacyConfigurationWithoutPassword) {
    Write-Host "Existing one-folder data was detected without stored bootstrap credentials."
    Write-Host "No user or password was changed. If no administrator exists, run:"
    Write-Host "  docker compose --env-file `"$envFile`" -f `"$composeFile`" exec app flask --app run.py user bootstrap-admin --email $AdminEmail"
  } else {
    Write-Host "Existing administrator bootstrap settings were retained."
    Write-Host "TinyMRP does not reset an existing user's password during restart."
  }
  Write-Host ""
  Write-Host "To stop:"
  Write-Host "  docker compose --env-file `"$envFile`" -f `"$composeFile`" down"
} finally {
  Pop-Location
}
