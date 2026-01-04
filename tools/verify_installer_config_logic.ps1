$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$issPath = Join-Path $root "solidworks-addin\installer.iss"
$configPath = Join-Path $root "solidworks-addin\TinyMRP.SolidWorksAddin\Services\TinyMrpConfig.cs"

if (-not (Test-Path $issPath)) {
  Write-Error "installer.iss not found at $issPath"
}

$iss = Get-Content -Raw -Path $issPath

$checks = @(
  @{ Name = "ProgramData config path"; Pattern = "{commonappdata}\\TinyMRP\\TinyMRP_config.txt" },
  @{ Name = "Override checkbox"; Pattern = "Override existing TinyMRP settings" },
  @{ Name = "Backend URL field"; Pattern = "Backend URL" },
  @{ Name = "Auth token field"; Pattern = "Auth token" },
  @{ Name = "BackendUrl key"; Pattern = "BackendUrl=" },
  @{ Name = "AuthToken key"; Pattern = "AuthToken=" }
)

Write-Host "Installer config logic checks:"
foreach ($check in $checks) {
  $ok = $iss -match [Regex]::Escape($check.Pattern)
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
