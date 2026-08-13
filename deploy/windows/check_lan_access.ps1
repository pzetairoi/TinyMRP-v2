<#
.SYNOPSIS
    Diagnose why other machines can or cannot reach this TinyMRP host.

.DESCRIPTION
    Read-only. It changes nothing; it prints the remediation commands instead.

    "It works on the server but nobody else can open it" almost never has an
    interesting cause. It is one of six things, and this checks all of them:

      1. The network is classified Public, so firewall rules scoped to
         Domain/Private never apply. This is the big one, and nothing in
         Windows tells you about it.
      2. There is no inbound allow rule for the port at all.
      3. A Block rule wins. Windows evaluates Block before Allow, whatever the
         order in the list.
      4. The service is bound to 127.0.0.1 instead of 0.0.0.0, so it is not
         listening on the network in the first place.
      5. TINYMRP_URL does not match the address users type, so they reach the
         site and then cannot log in.
      6. The host name does not resolve on client machines.

.PARAMETER Port
    The port clients connect to. 80 for the nginx/service deployment, or the
    published port for a Docker Desktop install (5000 by default).

.PARAMETER EnvFile
    TinyMRP environment file to cross-check TINYMRP_URL against. Defaults to
    C:\TinyMRP\config\.env.lan, and falls back to the Community .env beside
    this repository's deploy\community\compose.yaml.

.PARAMETER Deployment
    'service' (nginx + waitress) or 'docker' (Docker Desktop). Auto-detected
    when omitted.

.EXAMPLE
    .\check_lan_access.ps1
.EXAMPLE
    .\check_lan_access.ps1 -Port 5000 -Deployment docker
#>
[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 0,
    [string]$EnvFile = '',
    [ValidateSet('service', 'docker', 'auto')]
    [string]$Deployment = 'auto'
)

$ErrorActionPreference = 'Stop'
$script:Problems = @()
$script:Warnings = @()

function Write-Section([string]$Title) {
    Write-Host ''
    Write-Host "== $Title " -NoNewline
    Write-Host ('=' * [Math]::Max(4, 60 - $Title.Length))
}
function Write-Ok([string]$Message)   { Write-Host "  [ OK ] $Message" }
function Write-Bad([string]$Message)  { Write-Host "  [FAIL] $Message"; $script:Problems += $Message }
function Write-Warn([string]$Message) { Write-Host "  [WARN] $Message"; $script:Warnings += $Message }
function Write-Info([string]$Message) { Write-Host "         $Message" }

# ---------------------------------------------------------------- discovery --
Write-Section 'Deployment'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $EnvFile) {
    foreach ($candidate in @('C:\TinyMRP\config\.env.lan', (Join-Path $repoRoot 'deploy\community\.env'))) {
        if (Test-Path -LiteralPath $candidate) { $EnvFile = $candidate; break }
    }
}

$envValues = @{}
if ($EnvFile -and (Test-Path -LiteralPath $EnvFile)) {
    foreach ($line in Get-Content -LiteralPath $EnvFile) {
        if ($line -match '^\s*([A-Z0-9_]+)\s*=\s*(.*)$') {
            $envValues[$Matches[1]] = $Matches[2].Trim().Trim('"')
        }
    }
    Write-Ok "Configuration: $EnvFile"
} else {
    Write-Warn 'No TinyMRP environment file found; TINYMRP_URL cannot be cross-checked.'
    Write-Info 'Pass -EnvFile <path> to check it.'
}

if ($Deployment -eq 'auto') {
    if ($envValues.ContainsKey('ACCESS_MODE') -or $envValues.ContainsKey('APP_BIND_IP')) { $Deployment = 'docker' }
    elseif (Get-Service -Name 'TinyMRP-App' -ErrorAction SilentlyContinue) { $Deployment = 'service' }
    else { $Deployment = 'service' }
}
Write-Ok "Deployment type: $Deployment"

if ($Port -eq 0) {
    if ($envValues.ContainsKey('APP_PORT')) { $Port = [int]$envValues['APP_PORT'] }
    elseif ($Deployment -eq 'docker')       { $Port = 5000 }
    else                                    { $Port = 80 }
}
Write-Ok "Client-facing port: $Port"

# ------------------------------------------------------- 1. network profile --
Write-Section '1. Network profile (the usual culprit)'

$profiles = Get-NetConnectionProfile
$activeCategories = @($profiles | Select-Object -ExpandProperty NetworkCategory -Unique)
foreach ($p in $profiles) {
    $line = "{0,-24} {1,-22} {2}" -f $p.Name, $p.InterfaceAlias, $p.NetworkCategory
    if ($p.NetworkCategory -eq 'Public') { Write-Warn $line } else { Write-Ok $line }
}
if ($activeCategories -contains 'Public') {
    Write-Info ''
    Write-Info 'Windows applies a firewall rule only on the profile(s) it is scoped to.'
    Write-Info 'A rule scoped to Domain/Private does nothing while the network is Public,'
    Write-Info 'and Windows gives no warning about it. Reclassify the office network:'
    Write-Info ''
    Write-Info '  Get-NetConnectionProfile'
    Write-Info '  Set-NetConnectionProfile -InterfaceAlias "<alias>" -NetworkCategory Private'
    Write-Info ''
    Write-Info 'Do this only for a network you trust. Never mark a hotel or cafe Private.'
}

# ---------------------------------------------------------- 2. and 3. rules --
Write-Section '2. Inbound firewall rules for this port'

$portFilters = Get-NetFirewallPortFilter -ErrorAction SilentlyContinue |
    Where-Object { $_.Protocol -eq 'TCP' -and $_.LocalPort -contains "$Port" }
$portRules = @()
foreach ($filter in $portFilters) {
    $rule = $filter | Get-NetFirewallRule -ErrorAction SilentlyContinue
    if ($rule -and $rule.Direction -eq 'Inbound') { $portRules += $rule }
}

$allowRules = @($portRules | Where-Object { $_.Action -eq 'Allow' -and $_.Enabled -eq 'True' })
$blockRules = @($portRules | Where-Object { $_.Action -eq 'Block' -and $_.Enabled -eq 'True' })

if ($blockRules) {
    foreach ($rule in $blockRules) {
        Write-Bad "BLOCK rule '$($rule.DisplayName)' (profile: $($rule.Profile)) covers port $Port."
    }
    Write-Info 'Windows evaluates Block before Allow, so this wins no matter what else exists.'
    Write-Info "  Remove-NetFirewallRule -DisplayName '<name>'"
} else {
    Write-Ok "No blocking rule covers port $Port."
}

if (-not $allowRules) {
    if ($Deployment -eq 'docker') {
        Write-Warn "No port-specific allow rule for $Port. Docker Desktop usually publishes"
        Write-Info 'through its own rules for com.docker.backend, so this can still work:'
        $dockerRules = Get-NetFirewallRule -Direction Inbound -Enabled True -ErrorAction SilentlyContinue |
            Where-Object { $_.DisplayName -match 'Docker Desktop' }
        if ($dockerRules) {
            foreach ($rule in $dockerRules) { Write-Info "  '$($rule.DisplayName)' profile: $($rule.Profile)" }
        } else {
            Write-Bad 'and no Docker Desktop inbound rules exist either. Nothing will get in.'
        }
    } else {
        Write-Bad "No enabled inbound ALLOW rule for TCP $Port. Other machines cannot connect."
        Write-Info 'Create one (elevated), scoped to your subnet:'
        Write-Info "  .\configure_firewall_lan.ps1 -LanRemoteRanges 192.168.0.0/24 -HttpPort $Port"
    }
} else {
    foreach ($rule in $allowRules) {
        $ruleProfiles = @($rule.Profile.ToString() -split ',\s*')
        $applies = ($ruleProfiles -contains 'Any') -or
                   ($activeCategories | Where-Object { $ruleProfiles -contains $_ })
        # PowerShell 5.1 cannot parse a double quote inside $() inside a
        # double-quoted string, so join outside the string.
        $activeText = $activeCategories -join ', '
        if ($applies) {
            Write-Ok "ALLOW '$($rule.DisplayName)' (profile: $($rule.Profile)) applies on this network."
        } else {
            Write-Bad "ALLOW '$($rule.DisplayName)' is scoped to '$($rule.Profile)' but this network is '$activeText' - it is INERT."
            Write-Info 'Either reclassify the network (section 1) or rescope the rule:'
            Write-Info "  Set-NetFirewallRule -DisplayName '$($rule.DisplayName)' -Profile Domain,Private,Public"
        }
        $remote = ($rule | Get-NetFirewallAddressFilter).RemoteAddress
        if ($remote -and $remote -ne 'Any') { Write-Info "         restricted to: $($remote -join ', ')" }
    }
}

# ---------------------------------------------------------------- 4. binding --
Write-Section '3. Is anything actually listening on the network?'

$listeners = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if (-not $listeners) {
    Write-Bad "Nothing is listening on TCP $Port. Start the service or the container stack."
    if ($Deployment -eq 'service') { Write-Info '  Start-Service TinyMRP-App;  cd C:\nginx; .\nginx.exe' }
    else { Write-Info '  cd deploy\community; .\tinymrp.ps1 start' }
} else {
    $addresses = @($listeners | Select-Object -ExpandProperty LocalAddress -Unique)
    if (($addresses -contains '0.0.0.0') -or ($addresses -contains '::')) {
        Write-Ok "Listening on all interfaces ($($addresses -join ', '))."
    } else {
        Write-Bad "Listening only on $($addresses -join ', ') - loopback only, so no other machine can connect."
        if ($Deployment -eq 'docker') {
            Write-Info 'The Community installer binds 127.0.0.1 in localhost mode. Set APP_BIND_IP="0.0.0.0"'
            Write-Info 'and ACCESS_MODE="lan" in .env (and TINYMRP_URL to the LAN address), then restart.'
        } else {
            Write-Info 'nginx must listen on 0.0.0.0:80. Check the listen directive in nginx.conf.'
        }
    }
}

foreach ($private in @(8000, 27017)) {
    $exposed = Get-NetTCPConnection -State Listen -LocalPort $private -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalAddress -in @('0.0.0.0', '::') }
    if ($exposed) {
        Write-Warn "TCP $private is listening on all interfaces. It should be loopback-only."
        if ($private -eq 27017) { Write-Info '  Set bindIp: 127.0.0.1 in mongod.cfg and restart MongoDB.' }
        else { Write-Info '  Waitress should bind 127.0.0.1; nginx is the only public listener.' }
    } else {
        Write-Ok "TCP $private is not exposed to the network."
    }
}

# ------------------------------------------------------------ 5. TINYMRP_URL --
Write-Section '4. Does TINYMRP_URL match how users reach this host?'

$declared = $envValues['TINYMRP_URL']
if (-not $declared) {
    Write-Bad 'TINYMRP_URL is not set. The app then assumes HTTPS, marks session cookies Secure,'
    Write-Info 'and every login over plain HTTP bounces straight back to the login form.'
    Write-Info '  Set TINYMRP_URL=http://<host-or-ip>[:port] in your environment file and restart.'
} else {
    Write-Ok "TINYMRP_URL = $declared"
    try {
        $uri = [Uri]$declared
        if ($uri.Scheme -eq 'https') {
            Write-Warn 'Scheme is https. Correct only if TLS really terminates in front of the app.'
            Write-Info 'On a plain-HTTP deployment this is THE cause of the endless login loop.'
        }
        $declaredPort = if ($uri.IsDefaultPort) { if ($uri.Scheme -eq 'https') { 443 } else { 80 } } else { $uri.Port }
        if ($declaredPort -ne $Port) {
            Write-Bad "TINYMRP_URL port ($declaredPort) does not match the client-facing port ($Port)."
            Write-Info 'The origin includes the port; a mismatch breaks login the same way.'
        } else {
            Write-Ok "Port in TINYMRP_URL matches ($declaredPort)."
        }

        $hostName = $uri.Host
        $resolved = $null
        try { $resolved = [System.Net.Dns]::GetHostAddresses($hostName) } catch { }
        if ($resolved) {
            Write-Ok "$hostName resolves here to $(($resolved | Select-Object -ExpandProperty IPAddressToString) -join ', ')"
            Write-Info 'Confirm it resolves on the CLIENT machines too, not just this one.'
        } else {
            Write-Bad "$hostName does not resolve on this machine."
            Write-Info 'Add an internal DNS A record, or a hosts entry on every client:'
            Write-Info "  <server-ip>  $hostName"
        }
    } catch {
        Write-Bad "TINYMRP_URL is not a valid absolute URL. It must include http:// or https://."
    }
}

# ------------------------------------------------------------- local probe ---
Write-Section '5. Local response check'

$addressesToTry = @('127.0.0.1') + @(
    Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
        Select-Object -ExpandProperty IPAddress
)
foreach ($address in $addressesToTry) {
    $url = "http://${address}:$Port/api/health"
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
        Write-Ok "$url -> $($response.StatusCode)"
    } catch {
        Write-Warn "$url -> no response ($($_.Exception.Message.Split([Environment]::NewLine)[0]))"
    }
}
Write-Info ''
Write-Info 'These are loopback and local-interface checks. They pass even when the'
Write-Info 'firewall blocks everyone else, so they cannot prove remote access.'
Write-Info 'From a SECOND machine on the LAN, run:'
Write-Info "  Test-NetConnection <server-ip> -Port $Port"
Write-Info "  curl http://<server-ip>:$Port/api/health"

# ------------------------------------------------------------------ verdict --
Write-Section 'Verdict'

if ($script:Problems.Count -eq 0 -and $script:Warnings.Count -eq 0) {
    Write-Host '  Nothing found. If clients still cannot connect, look outside this host:'
    Write-Host '  a router/VLAN ACL, client-side security software, or wireless client isolation'
    Write-Host '  (common on guest Wi-Fi: it blocks device-to-device traffic entirely).'
} else {
    if ($script:Problems.Count) {
        Write-Host "  $($script:Problems.Count) problem(s) that will stop other machines connecting:"
        foreach ($p in $script:Problems) { Write-Host "    - $p" }
    }
    if ($script:Warnings.Count) {
        Write-Host "  $($script:Warnings.Count) warning(s) worth reviewing:"
        foreach ($w in $script:Warnings) { Write-Host "    - $w" }
    }
}
Write-Host ''
Write-Host '  Full guide: docs/deployment/03-windows-lan.md'
Write-Host '  Reachability FAQ: docs/deployment/11-faq.md'
Write-Host ''

if ($script:Problems.Count) { exit 1 }
exit 0
