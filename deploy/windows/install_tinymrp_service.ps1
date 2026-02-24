[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$AppRoot,
    [Parameter(Mandatory = $true)]
    [string]$EnvFile,
    [string]$ServiceName = "TinyMRP-App",
    [string]$DisplayName = "TinyMRP Application Service",
    [string]$ServiceUser = "LocalSystem",
    [string]$ServicePassword = "",
    [int]$Threads = 8,
    [int]$ConnectionLimit = 400,
    [int]$ChannelTimeout = 120,
    [switch]$ReplaceExisting
)

$ErrorActionPreference = "Stop"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdmin) {
    throw "Run this script from an elevated PowerShell session."
}

function Invoke-Sc {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    Write-Host "sc.exe $($Args -join ' ')"
    $output = & sc.exe @Args 2>&1
    $text = ($output | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "sc.exe failed: $text"
    }
    if ($text) {
        Write-Host $text
    }
}

if (-not (Test-Path -LiteralPath $AppRoot)) {
    throw "AppRoot not found: $AppRoot"
}
if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Env file not found: $EnvFile"
}

$launcher = Join-Path $AppRoot "deploy\windows\run_waitress_service.ps1"
if (-not (Test-Path -LiteralPath $launcher)) {
    throw "Launcher not found: $launcher"
}

$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existing) {
    if (-not $ReplaceExisting) {
        throw "Service '$ServiceName' already exists. Re-run with -ReplaceExisting to recreate it."
    }
    if ($existing.Status -ne "Stopped") {
        Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    }
    Invoke-Sc "delete" $ServiceName
    Start-Sleep -Seconds 2
}

$binPath = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$launcher`" -AppRoot `"$AppRoot`" -EnvFile `"$EnvFile`" -Threads $Threads -ConnectionLimit $ConnectionLimit -ChannelTimeout $ChannelTimeout"

if ($ServiceUser -eq "LocalSystem") {
    Invoke-Sc "create" $ServiceName "binPath= $binPath" "start= auto" "DisplayName= $DisplayName"
} else {
    if ([string]::IsNullOrWhiteSpace($ServicePassword)) {
        throw "ServicePassword is required when ServiceUser is not LocalSystem."
    }
    Invoke-Sc "create" $ServiceName "binPath= $binPath" "start= auto" "DisplayName= $DisplayName" "obj= $ServiceUser" "password= $ServicePassword"
}

# Restart service automatically on failures.
Invoke-Sc "failure" $ServiceName "reset= 86400" "actions= restart/5000/restart/5000/restart/5000"
Invoke-Sc "failureflag" $ServiceName "1"

Start-Service -Name $ServiceName
Write-Host "Service '$ServiceName' installed and started."
