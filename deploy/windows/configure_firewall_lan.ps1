[CmdletBinding()]
param(
    [string]$RuleGroup = "TinyMRP LAN",
    [string]$LanRemoteRanges = "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16",
    [int]$HttpPort = 80,
    [int]$AppPort = 8000,
    [int]$MongoPort = 27017
)

$ErrorActionPreference = "Stop"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdmin) {
    throw "Run this script from an elevated PowerShell session."
}

Write-Host "Removing old firewall rules in group '$RuleGroup' (if any)..."
Get-NetFirewallRule -Group $RuleGroup -ErrorAction SilentlyContinue | Remove-NetFirewallRule

Write-Host "Allowing inbound HTTP on TCP/$HttpPort only from: $LanRemoteRanges"
New-NetFirewallRule `
    -DisplayName "TinyMRP HTTP Inbound" `
    -Group $RuleGroup `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort $HttpPort `
    -RemoteAddress $LanRemoteRanges `
    -Profile Domain,Private

Write-Host "Blocking direct inbound app port TCP/$AppPort from all remotes."
New-NetFirewallRule `
    -DisplayName "TinyMRP Block App Port" `
    -Group $RuleGroup `
    -Direction Inbound `
    -Action Block `
    -Protocol TCP `
    -LocalPort $AppPort `
    -RemoteAddress Any `
    -Profile Any

Write-Host "Blocking direct inbound MongoDB port TCP/$MongoPort from all remotes."
New-NetFirewallRule `
    -DisplayName "TinyMRP Block Mongo Port" `
    -Group $RuleGroup `
    -Direction Inbound `
    -Action Block `
    -Protocol TCP `
    -LocalPort $MongoPort `
    -RemoteAddress Any `
    -Profile Any

Write-Host "Firewall LAN policy applied."
