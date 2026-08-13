[CmdletBinding()]
param(
    [string]$RuleGroup = "TinyMRP LAN",
    [string]$LanRemoteRanges = "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16",
    [int]$HttpPort = 80,
    [int]$AppPort = 8000,
    [int]$MongoPort = 27017,
    # Also apply the allow rule on the Public profile. Needed when Windows has
    # classified the office network Public and you cannot reclassify it.
    # The rule stays restricted to -LanRemoteRanges either way.
    [switch]$IncludePublicProfile
)

$ErrorActionPreference = "Stop"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdmin) {
    throw "Run this script from an elevated PowerShell session."
}

# Windows applies a rule only on the profile(s) it is scoped to, and warns
# about nothing when none of them are active. A Domain/Private rule on a
# network Windows has classified Public is inert, so the deployment looks
# correct and no other machine can connect. This is the single most common
# reason a Windows LAN install is unreachable.
$AllowedProfiles = @('Domain', 'Private')
$publicProfiles = @(Get-NetConnectionProfile -ErrorAction SilentlyContinue |
    Where-Object { $_.NetworkCategory -eq 'Public' })
if ($publicProfiles) {
    Write-Warning "These connections are classified Public, where a Domain/Private rule does nothing:"
    $publicProfiles | ForEach-Object { Write-Warning "  $($_.InterfaceAlias)  ($($_.Name))" }
    Write-Host ''
    Write-Host 'Preferred fix, if this is a network you trust:'
    Write-Host ('  Set-NetConnectionProfile -InterfaceAlias "' + $publicProfiles[0].InterfaceAlias + '" -NetworkCategory Private')
    Write-Host ''
    if ($IncludePublicProfile) {
        Write-Warning 'Continuing with -IncludePublicProfile: the rule will also apply on Public networks.'
        $AllowedProfiles += 'Public'
    } else {
        Write-Warning 'The rules below will NOT take effect until you reclassify the network,'
        Write-Warning 'or re-run this script with -IncludePublicProfile.'
    }
    Write-Host ''
}
$ProfileList = $AllowedProfiles -join ','

Write-Host "Removing old firewall rules in group '$RuleGroup' (if any)..."
Get-NetFirewallRule -Group $RuleGroup -ErrorAction SilentlyContinue | Remove-NetFirewallRule

Write-Host "Allowing inbound HTTP on TCP/$HttpPort only from: $LanRemoteRanges (profiles: $ProfileList)"
New-NetFirewallRule `
    -DisplayName "TinyMRP HTTP Inbound" `
    -Group $RuleGroup `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort $HttpPort `
    -RemoteAddress $LanRemoteRanges `
    -Profile $AllowedProfiles

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
