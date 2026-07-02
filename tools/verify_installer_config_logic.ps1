$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$issPath = Join-Path $root "solidworks-addin\installer.iss"
$configPath = Join-Path $root "solidworks-addin\TinyMRP.SolidWorksAddin\Services\TinyMrpConfig.cs"

if (-not (Test-Path $issPath)) {
  Write-Error "installer.iss not found at $issPath"
}

$iss = Get-Content -Raw -Path $issPath

$checks = @(
  @{
    Name = "ProgramData config path"
    Patterns = @(
      "{commonappdata}\\TinyMRP\\TinyMRP_config.txt",
      "{commonappdata}\TinyMRP\{#ConfigFileName}"
    )
  },
  @{ Name = "Override checkbox"; Patterns = @("Override existing TinyMRP settings") },
  @{ Name = "Backend URL field"; Patterns = @("Backend URL") },
  @{ Name = "Auth token field"; Patterns = @("Auth token") },
  @{ Name = "BackendUrl key"; Patterns = @("BackendUrl=") },
  @{ Name = "AuthToken key"; Patterns = @("AuthToken=") }
)

Write-Host "Installer config logic checks:"
foreach ($check in $checks) {
  $ok = $false
  foreach ($pattern in $check.Patterns) {
    if ($iss -match [Regex]::Escape($pattern)) {
      $ok = $true
      break
    }
  }
  $status = if ($ok) { "OK" } else { "MISSING" }
  Write-Host ("- {0}: {1}" -f $check.Name, $status)
}

if (Test-Path $configPath) {
  $cfg = Get-Content -Raw -Path $configPath
  $readsProgramData = $cfg -match "CommonApplicationData"
  Write-Host ("- Add-in reads ProgramData: {0}" -f ($(if ($readsProgramData) { "OK" } else { "MISSING" })))
} else {
  Write-Host "- Add-in config file not found to verify read order."
}

Write-Host "Expected config target: $([Environment]::GetFolderPath('CommonApplicationData'))\\TinyMRP\\TinyMRP_config.txt"
