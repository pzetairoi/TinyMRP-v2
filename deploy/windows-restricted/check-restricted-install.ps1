<#
.SYNOPSIS
    Pre-flight and post-mortem for a run.py TinyMRP install on a locked-down
    Windows host.

.DESCRIPTION
    Read-only. It changes nothing and prints the fix for anything it finds.

    Run it BEFORE the first start to catch a configuration that cannot work,
    and AFTER an update to confirm nothing regressed. It checks, in order:

      1. Python, the virtualenv and the required packages
      2. The environment file: the four values that must be set, and the two
         that break login when they are wrong
      3. MongoDB reachability, and that it is not exposed to the network
      4. The deliverables folder and whether this account can write to it
      5. Port availability, and what is already listening
      6. Windows Firewall and the network profile, which decide whether
         anyone else can reach the port at all
      7. Name resolution for the host in TINYMRP_URL
      8. A live response check when the server is already running

.PARAMETER EnvFile
    Environment file to inspect. Default C:\TinyMRP\config\.env.lan.

.PARAMETER AppRoot
    Repository checkout. Defaults to two levels above this script.

.EXAMPLE
    .\check-restricted-install.ps1
.EXAMPLE
    .\check-restricted-install.ps1 -EnvFile D:\cfg\.env.lan
#>
[CmdletBinding()]
param(
    [string]$EnvFile = 'C:\TinyMRP\config\.env.lan',
    [string]$AppRoot = ''
)

$ErrorActionPreference = 'Stop'
$script:Problems = @()
$script:Warnings = @()

function Write-Section([string]$Title) {
    Write-Host ''
    Write-Host "== $Title " -NoNewline
    Write-Host ('=' * [Math]::Max(4, 62 - $Title.Length))
}
function Write-Ok([string]$m)   { Write-Host "  [ OK ] $m" }
function Write-Bad([string]$m)  { Write-Host "  [FAIL] $m"; $script:Problems += $m }
function Write-Warn([string]$m) { Write-Host "  [WARN] $m"; $script:Warnings += $m }
function Write-Info([string]$m) { Write-Host "         $m" }

if (-not $AppRoot) { $AppRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path }

# ------------------------------------------------------------- 1. runtime --
Write-Section '1. Python runtime'

if (-not (Test-Path -LiteralPath (Join-Path $AppRoot 'run.py'))) {
    Write-Bad "run.py not found under $AppRoot. Pass -AppRoot <repo folder>."
} else {
    Write-Ok "Application root: $AppRoot"
}

$python = Join-Path $AppRoot '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $python) {
    Write-Ok "Virtualenv interpreter: $python"
} else {
    $fallback = Get-Command python -ErrorAction SilentlyContinue
    if ($fallback) {
        Write-Warn "No .venv found; falling back to $($fallback.Source)"
        Write-Info 'A virtualenv keeps TinyMRP dependencies off the system interpreter:'
        Write-Info "  cd $AppRoot;  py -3.12 -m venv .venv"
        Write-Info '  .\.venv\Scripts\python.exe -m pip install -r requirements.txt'
        $python = $fallback.Source
    } else {
        Write-Bad 'No Python interpreter found. Install Python 3.11 or 3.12.'
        $python = $null
    }
}

if ($python) {
    $version = (& $python -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null)
    if ($version -in @('3.11', '3.12')) { Write-Ok "Python $version" }
    elseif ($version) { Write-Warn "Python $version is untested; 3.11 or 3.12 are what the deployments use." }

    foreach ($package in @('flask', 'mongoengine', 'waitress')) {
        $probe = & $python -c "import importlib;importlib.import_module('$package');print('ok')" 2>$null
        if ($probe -eq 'ok') {
            Write-Ok "package $package"
        } elseif ($package -eq 'waitress') {
            Write-Warn 'waitress is not installed; run.py will fall back to the Flask development server.'
            Write-Info 'waitress is pure Python and already listed in requirements.txt, so it needs'
            Write-Info 'no new approved executable - it runs inside this same python.exe:'
            Write-Info "  $python -m pip install waitress"
        } else {
            Write-Bad "package $package is missing. Run: $python -m pip install -r requirements.txt"
        }
    }
}

# --------------------------------------------------------- 2. environment --
Write-Section '2. Environment file'

$envValues = @{}
if (-not (Test-Path -LiteralPath $EnvFile)) {
    Write-Bad "Environment file not found: $EnvFile"
    Write-Info 'Copy the template and edit the four REQUIRED values:'
    Write-Info "  copy $AppRoot\deploy\windows-restricted\.env.restricted.example $EnvFile"
} else {
    Write-Ok "Environment file: $EnvFile"
    foreach ($line in Get-Content -LiteralPath $EnvFile) {
        if ($line -match '^\s*([A-Z0-9_]+)\s*=\s*(.*)$') {
            $envValues[$Matches[1]] = $Matches[2].Trim().Trim('"')
        }
    }

    foreach ($name in @('SECRET_KEY', 'SECURITY_PASSWORD_SALT')) {
        $value = $envValues[$name]
        if (-not $value) {
            Write-Bad "$name is not set. The app refuses to start without it."
            Write-Info 'It is never generated: a key invented at boot changes on restart, and an'
            Write-Info 'app that re-keys itself cannot tell a forged session from a real one.'
            Write-Info '  powershell -c "[guid]::NewGuid().ToString(''N'') + [guid]::NewGuid().ToString(''N'')"'
        } elseif ($value.Length -lt 16) {
            Write-Bad "$name is only $($value.Length) characters; 16 is the minimum, 32+ is sensible."
        } elseif ($value -match '^REPLACE-WITH') {
            Write-Bad "$name still holds the template placeholder."
        } else {
            Write-Ok "$name set ($($value.Length) characters)"
        }
    }
    if ($envValues['SECRET_KEY'] -and $envValues['SECRET_KEY'] -eq $envValues['SECURITY_PASSWORD_SALT']) {
        Write-Bad 'SECRET_KEY and SECURITY_PASSWORD_SALT are identical. They must be independent values.'
    }

    $declared = $envValues['TINYMRP_URL']
    if (-not $declared) {
        Write-Bad 'TINYMRP_URL is not set. This is the single most common cause of "login just returns to the login page".'
        Write-Info 'Unset means TinyMRP assumes HTTPS: it marks the session cookie Secure, the'
        Write-Info 'browser discards it on a plain-HTTP origin, and the login POST then fails with'
        Write-Info '"CSRF session token is missing". Set it to the address users type:'
        Write-Info '  TINYMRP_URL=http://tinymrp.local:5555'
    } else {
        Write-Ok "TINYMRP_URL = $declared"
        try {
            $uri = [Uri]$declared
            if ($uri.Scheme -eq 'https') {
                Write-Bad 'TINYMRP_URL says https but this deployment terminates no TLS.'
                Write-Info 'Session cookies would be marked Secure and discarded by the browser.'
                Write-Info 'Use http:// unless you have put a TLS proxy in front.'
            } else {
                Write-Ok 'Scheme is http, which matches a plain run.py deployment.'
            }
            if ($uri.IsDefaultPort -and $declared -notmatch ':\d+') {
                Write-Info "No port in the URL, so run.py will listen on 80."
            } else {
                Write-Ok "Port $($uri.Port) - run.py derives its listening port from this."
            }
        } catch {
            Write-Bad 'TINYMRP_URL is not a valid absolute URL. It must start with http:// or https://.'
        }
    }

    $hops = $envValues['TINYMRP_TRUSTED_PROXY_HOPS']
    if ($hops -eq '0') {
        Write-Ok 'TINYMRP_TRUSTED_PROXY_HOPS = 0 (nothing in front of this process)'
    } elseif (-not $hops) {
        Write-Warn 'TINYMRP_TRUSTED_PROXY_HOPS is unset, so it defaults to 1 (assumes a reverse proxy).'
        Write-Info 'With nothing in front, a client can send its own X-Forwarded-For and get a'
        Write-Info 'private rate-limit bucket. Set TINYMRP_TRUSTED_PROXY_HOPS=0.'
    } else {
        Write-Warn "TINYMRP_TRUSTED_PROXY_HOPS = $hops. Use 0 unless a proxy you control sits in front."
    }

    if ($envValues['FORCE_HTTPS'] -and $envValues['FORCE_HTTPS'] -notin @('false', '0', 'no', 'off')) {
        Write-Bad 'FORCE_HTTPS is on, so every request is redirected to https:// - which nothing serves here.'
    }
    if ($envValues['TINYMRP_DEV'] -and $envValues['TINYMRP_DEV'] -in @('1', 'true', 'yes', 'on')) {
        Write-Bad 'TINYMRP_DEV is on. run.py refuses to combine the Flask debugger with a network bind.'
        Write-Info "Werkzeug's traceback console runs arbitrary Python in the server process."
    }
}

# ------------------------------------------------------------- 3. MongoDB --
Write-Section '3. MongoDB'

$mongoUri = $envValues['MONGO_URI']
if (-not $mongoUri) {
    Write-Warn 'MONGO_URI is unset; the app will default to mongodb://localhost:27017/tinymrp-v2.'
    $mongoUri = 'mongodb://localhost:27017/tinymrp-v2'
} else {
    Write-Ok "MONGO_URI host: $(([Uri]$mongoUri).Host):$(([Uri]$mongoUri).Port)"
}

$service = Get-Service -Name 'MongoDB' -ErrorAction SilentlyContinue
if ($service) {
    if ($service.Status -eq 'Running') { Write-Ok 'MongoDB service is running.' }
    else { Write-Bad "MongoDB service is $($service.Status). Start-Service MongoDB" }
} else {
    Write-Warn 'No local MongoDB service found (fine if the database is on another host).'
}

$mongoPort = 27017
try { $mongoPort = ([Uri]$mongoUri).Port } catch { }
$exposed = Get-NetTCPConnection -State Listen -LocalPort $mongoPort -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalAddress -in @('0.0.0.0', '::') }
if ($exposed) {
    Write-Bad "MongoDB is listening on all interfaces (port $mongoPort). Anyone who can reach it has full data access."
    Write-Info '  Set  net: bindIp: 127.0.0.1  in mongod.cfg and restart the service.'
} else {
    Write-Ok "MongoDB is not exposed to the network (port $mongoPort)."
}

# -------------------------------------------------------- 4. deliverables --
Write-Section '4. Deliverables folder'

$root = $envValues['FILES_LOCAL_ROOT']
if (-not $root) {
    Write-Bad 'FILES_LOCAL_ROOT is not set. TinyMRP has nowhere to read or write CAD files.'
} else {
    $native = $root.Replace('/', '\')
    if (-not (Test-Path -LiteralPath $native)) {
        Write-Bad "FILES_LOCAL_ROOT does not exist: $native"
        Write-Info "  New-Item -ItemType Directory -Force -Path '$native'"
    } else {
        Write-Ok "FILES_LOCAL_ROOT: $native"
        $probe = Join-Path $native ".tinymrp-write-test"
        try {
            Set-Content -LiteralPath $probe -Value 'x' -ErrorAction Stop
            Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue
            Write-Ok "Writable by $env:USERNAME (thumbnails and uploads land here)."
        } catch {
            Write-Bad "Not writable by $env:USERNAME. Uploads and thumbnails will fail."
            Write-Info "  icacls `"$native`" /grant `"$env:USERNAME`:(OI)(CI)M`""
        }
        $free = (Get-PSDrive -Name (Split-Path -Qualifier $native).TrimEnd(':') -ErrorAction SilentlyContinue).Free
        if ($free -ne $null) {
            $freeMb = [Math]::Round($free / 1MB)
            if ($freeMb -lt 512) { Write-Bad "Only ${freeMb} MB free. /api/ready fails below 512 MB." }
            else { Write-Ok "${freeMb} MB free on that volume." }
        }
    }
}

# ---------------------------------------------------------------- 5. port --
Write-Section '5. Listening port'

$port = 5000
if ($envValues['TINYMRP_BIND_PORT']) { $port = [int]$envValues['TINYMRP_BIND_PORT'] }
elseif ($envValues['TINYMRP_URL']) { try { $port = ([Uri]$envValues['TINYMRP_URL']).Port } catch { } }
Write-Ok "Expected port: $port"

$listeners = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
if (-not $listeners) {
    Write-Info 'Nothing is listening yet - expected if TinyMRP is not started.'
} else {
    $owners = $listeners | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($owner in $owners) {
        $proc = Get-Process -Id $owner -ErrorAction SilentlyContinue
        Write-Ok "Port $port held by $($proc.ProcessName) (pid $owner)"
    }
    $addresses = @($listeners | Select-Object -ExpandProperty LocalAddress -Unique)
    if (($addresses -contains '0.0.0.0') -or ($addresses -contains '::')) {
        Write-Ok "Listening on all interfaces ($($addresses -join ', '))."
    } else {
        Write-Bad "Listening only on $($addresses -join ', ') - no other machine can connect."
        Write-Info 'run.py binds 0.0.0.0 automatically when TINYMRP_URL names a non-loopback host.'
        Write-Info 'Override with TINYMRP_BIND_HOST=0.0.0.0 if you need to force it.'
    }
}

# ------------------------------------------------------------ 6. firewall --
Write-Section '6. Firewall and network profile'

$profiles = Get-NetConnectionProfile -ErrorAction SilentlyContinue
$activeCategories = @($profiles | Select-Object -ExpandProperty NetworkCategory -Unique)
foreach ($p in $profiles) {
    $line = "{0,-24} {1,-22} {2}" -f $p.Name, $p.InterfaceAlias, $p.NetworkCategory
    if ($p.NetworkCategory -eq 'Public') { Write-Warn $line } else { Write-Ok $line }
}
if ($activeCategories -contains 'Public') {
    Write-Info ''
    Write-Info 'Windows applies a firewall rule only on the profile(s) it is scoped to, and'
    Write-Info 'warns about nothing when none are active - so a Domain/Private rule is inert'
    Write-Info 'on a Public network. If this is a network you trust:'
    Write-Info '  Set-NetConnectionProfile -InterfaceAlias "<alias>" -NetworkCategory Private'
}

$portFilters = Get-NetFirewallPortFilter -ErrorAction SilentlyContinue |
    Where-Object { $_.Protocol -eq 'TCP' -and $_.LocalPort -contains "$port" }
$rules = @()
foreach ($filter in $portFilters) {
    $rule = $filter | Get-NetFirewallRule -ErrorAction SilentlyContinue
    if ($rule -and $rule.Direction -eq 'Inbound' -and $rule.Enabled -eq 'True') { $rules += $rule }
}
$blocked = @($rules | Where-Object { $_.Action -eq 'Block' })
$allowed = @($rules | Where-Object { $_.Action -eq 'Allow' })
foreach ($rule in $blocked) {
    Write-Bad "BLOCK rule '$($rule.DisplayName)' covers port $port. Block always beats Allow."
}
if (-not $allowed) {
    Write-Bad "No inbound ALLOW rule for TCP $port. Other machines cannot connect."
    Write-Info 'Ask IT for an inbound TCP allow rule scoped to the office subnet, or if you'
    Write-Info 'have rights, run elevated:'
    Write-Info "  New-NetFirewallRule -DisplayName 'TinyMRP ($port)' -Direction Inbound -Action Allow ``"
    Write-Info "    -Protocol TCP -LocalPort $port -Profile Domain,Private -RemoteAddress 192.168.0.0/24"
} else {
    $activeText = $activeCategories -join ', '
    foreach ($rule in $allowed) {
        $ruleProfiles = @($rule.Profile.ToString() -split ',\s*')
        $applies = ($ruleProfiles -contains 'Any') -or ($activeCategories | Where-Object { $ruleProfiles -contains $_ })
        if ($applies) { Write-Ok "ALLOW '$($rule.DisplayName)' (profile: $($rule.Profile)) applies here." }
        else { Write-Bad "ALLOW '$($rule.DisplayName)' is scoped to '$($rule.Profile)' but this network is '$activeText' - INERT." }
    }
}

# ------------------------------------------------------------------ 7. dns --
Write-Section '7. Name resolution'

if ($envValues['TINYMRP_URL']) {
    try {
        $hostName = ([Uri]$envValues['TINYMRP_URL']).Host
        $addresses = $null
        try { $addresses = [System.Net.Dns]::GetHostAddresses($hostName) } catch { }
        if ($addresses) {
            Write-Ok "$hostName resolves here to $(($addresses | Select-Object -ExpandProperty IPAddressToString) -join ', ')"
            $local = @(Get-NetIPAddress -AddressFamily IPv4 | Select-Object -ExpandProperty IPAddress)
            $match = $addresses | Where-Object { $local -contains $_.IPAddressToString }
            if (-not $match) {
                Write-Warn "$hostName does not resolve to an address on this machine."
                Write-Info 'Correct only if the name intentionally points somewhere else.'
            }
            Write-Info 'Confirm it resolves on the CLIENT machines too, not just here.'
        } else {
            Write-Bad "$hostName does not resolve on this machine."
            Write-Info 'Add an internal DNS A record, or a hosts entry on each client:'
            Write-Info "  <server-ip>  $hostName"
        }
    } catch { }
}

# ------------------------------------------------------------- 8. liveness --
Write-Section '8. Live response'

if ($listeners) {
    foreach ($target in @("http://127.0.0.1:$port/api/health", "$($envValues['TINYMRP_URL'])/api/health")) {
        if (-not $target -or $target -like '/api/health') { continue }
        try {
            $response = Invoke-WebRequest -Uri $target -UseBasicParsing -TimeoutSec 5
            Write-Ok "$target -> $($response.StatusCode)"
        } catch {
            Write-Warn "$target -> no response"
        }
    }
    try {
        $head = Invoke-WebRequest -Uri "http://127.0.0.1:$port/login" -UseBasicParsing -TimeoutSec 5
        $cookie = ($head.Headers['Set-Cookie'] | Out-String)
        if ($cookie -match 'Secure') {
            Write-Bad 'The session cookie is marked Secure on a plain-HTTP deployment. Login will loop.'
            Write-Info 'Set TINYMRP_URL to an http:// address and restart.'
        } elseif ($cookie) {
            Write-Ok 'Session cookie is storable over plain HTTP (no Secure flag).'
        }
        $csp = ($head.Headers['Content-Security-Policy'] | Out-String)
        if ($csp -match 'upgrade-insecure-requests') {
            Write-Bad 'The CSP asks browsers to upgrade assets to https. The page will render unstyled.'
        } elseif ($csp) {
            Write-Ok 'CSP does not force an https upgrade.'
        }
    } catch { }
} else {
    Write-Info 'TinyMRP is not running, so the response checks were skipped.'
    Write-Info "Start it with: $AppRoot\deploy\windows-restricted\start-tinymrp.cmd `"$EnvFile`""
}

# ------------------------------------------------------------------ verdict --
Write-Section 'Verdict'

if ($script:Problems.Count -eq 0 -and $script:Warnings.Count -eq 0) {
    Write-Host '  Nothing found. If users still cannot connect, look outside this host:'
    Write-Host '  a router or VLAN ACL, client security software, or wireless client isolation.'
} else {
    if ($script:Problems.Count) {
        Write-Host "  $($script:Problems.Count) problem(s) to fix:"
        foreach ($p in $script:Problems) { Write-Host "    - $p" }
    }
    if ($script:Warnings.Count) {
        Write-Host "  $($script:Warnings.Count) warning(s):"
        foreach ($w in $script:Warnings) { Write-Host "    - $w" }
    }
}
Write-Host ''
Write-Host '  Guide: docs/deployment/12-restricted-windows-flask.md'
Write-Host '  FAQ:   docs/deployment/11-faq.md'
Write-Host ''

if ($script:Problems.Count) { exit 1 }
exit 0
