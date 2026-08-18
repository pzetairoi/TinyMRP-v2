<#
.SYNOPSIS
    Guided TinyMRP Community install on Windows Docker Desktop (app + MongoDB + Redis).
#>
[CmdletBinding()]
param(
    [string]$DeliverablesPath,
    [ValidateSet('localhost', 'lan', 'domain')]
    [string]$AccessMode,
    [string]$Address,
    [ValidateRange(1, 65535)]
    [int]$Port = 5000,
    [string]$AdminEmail,
    [Security.SecureString]$AdministratorPassword,
    [string]$ImageRepository,
    [string]$Version,
    # Build the application image from this source checkout instead of pulling
    # a published release image. Use it when you cloned the repository rather
    # than downloading a versioned Community bundle.
    [switch]$Build,
    # Install the CV03 sample dataset and one demo login per role after the
    # first start, and print those passwords once. Evaluation instances only.
    [switch]$WithDemoData
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile = Join-Path $ScriptDir '.env'
$ComposeFile = Join-Path $ScriptDir 'compose.yaml'

function Stop-WithError([string]$Message) { throw $Message }
function Read-Default([string]$Prompt, [string]$Default) {
    $value = Read-Host "$Prompt [$Default]"
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value.Trim()
}
function Test-Port([int]$Number) {
    return $null -ne (Get-NetTCPConnection -State Listen -LocalPort $Number -ErrorAction SilentlyContinue | Select-Object -First 1)
}
function New-HexSecret([int]$Bytes = 32) {
    $buffer = New-Object byte[] $Bytes
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($buffer) } finally { $rng.Dispose() }
    return -join ($buffer | ForEach-Object { $_.ToString('x2') })
}
function Assert-SafeValue([string]$Value) {
    if ($Value.Contains("`r") -or $Value.Contains("`n") -or $Value.Contains('"') -or $Value.Contains('$') -or $Value.Contains('\')) {
        Stop-WithError 'Values cannot contain newlines, quotes, backslashes, or dollar signs.'
    }
}
function Add-EnvValue([Collections.Generic.List[string]]$Lines, [string]$Name, [string]$Value) {
    Assert-SafeValue $Value
    $Lines.Add("$Name=`"$Value`"")
}
function Get-ReleaseValue([string]$Name) {
    $releaseFile = Join-Path $ScriptDir 'release.env'
    if (-not (Test-Path -LiteralPath $releaseFile)) { return '' }
    $line = Get-Content -LiteralPath $releaseFile | Where-Object { $_ -like "$Name=*" } | Select-Object -First 1
    if ($line) { return $line.Substring($Name.Length + 1).Trim() }
    return ''
}
# A name no public certificate authority will ever issue for. Caddy detects
# these itself and signs them with its own CA instead of asking Let's Encrypt,
# which works but makes browsers warn until that CA is trusted. Kept in step
# with is_internal_domain() in install.sh.
function Test-InternalDomain([string]$Domain) {
    $d = $Domain.ToLowerInvariant()
    foreach ($suffix in @('.local', '.localdomain', '.localhost', '.internal', '.intranet',
                          '.lan', '.home.arpa', '.test', '.invalid', '.example',
                          '.example.com', '.example.org', '.example.net')) {
        if ($d.EndsWith($suffix)) { return $true }
    }
    return (-not $d.Contains('.'))
}
function Show-AccessModes {
    Write-Host @'

How will people reach this server? This answer decides everything else, so it
is worth thirty seconds.

  localhost  Only this machine, at http://localhost:<port>. For trying TinyMRP
             out. No other computer can reach it.

  lan        Any machine on your network, at http://<ip-or-name>:<port>.
             Plain HTTP, no certificate, ports 80 and 443 stay free.

  domain     Any machine, at https://<your-domain>, with TLS terminated by a
             Caddy reverse proxy this installer runs for you. Needs TCP 80 and
             443 free.
             - a public name (mrp.example.com) gets a real Let's Encrypt
               certificate automatically;
             - an internal-only name (mrp.company.local) gets one from Caddy's
               own authority, which browsers distrust until you install it.
               This installer prints exactly how, at the end.

'@
}
function Invoke-DockerCommand {
    $DockerArguments = @($args)
    $savedPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & docker @DockerArguments
        $exitCode = $LASTEXITCODE
    } finally { $ErrorActionPreference = $savedPreference }
    if ($exitCode -ne 0) { Stop-WithError "docker failed with exit code $exitCode." }
    return $output
}

if (Test-Path -LiteralPath $EnvFile) { Stop-WithError "$EnvFile already exists. Use tinymrp.ps1 for this installation." }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Stop-WithError 'Install and start Docker Desktop first.' }
& cmd.exe /d /c "docker info >nul 2>nul"; if ($LASTEXITCODE -ne 0) { Stop-WithError 'Docker Desktop is not running.' }
& cmd.exe /d /c "docker compose version >nul 2>nul"; if ($LASTEXITCODE -ne 0) { Stop-WithError 'Docker Compose v2 is required.' }

if (-not $DeliverablesPath) { $DeliverablesPath = Read-Default 'Deliverables folder' 'C:\TinyMRP\Deliverables' }
if (-not $AccessMode) { Show-AccessModes; $AccessMode = Read-Default 'Access mode (localhost/lan/domain)' 'localhost' }
if ($AccessMode -notin @('localhost', 'lan', 'domain')) { Stop-WithError 'Access mode must be localhost, lan, or domain.' }
if (Test-Port $Port) { Stop-WithError "TCP port $Port is already in use." }
if (-not $AdminEmail) { $AdminEmail = Read-Default 'Administrator email' 'admin@example.com' }
if ($AdminEmail -notmatch '^[^@\s]+@[^@\s]+\.[^@\s]+$') { Stop-WithError 'Enter a plausible administrator email address.' }
if (-not $AdministratorPassword) { $AdministratorPassword = Read-Host 'Administrator password (14+ characters)' -AsSecureString }
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($AdministratorPassword)
try { $plainAdminPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
if ($plainAdminPassword.Length -lt 14) { Stop-WithError 'Administrator password must be at least 14 characters.' }
Assert-SafeValue $plainAdminPassword

if (-not $ImageRepository) { $ImageRepository = if ($env:TINYMRP_IMAGE_REPOSITORY) { $env:TINYMRP_IMAGE_REPOSITORY } else { Get-ReleaseValue 'TINYMRP_IMAGE_REPOSITORY' } }
if (-not $Version) { $Version = if ($env:TINYMRP_VERSION) { $env:TINYMRP_VERSION } else { Get-ReleaseValue 'TINYMRP_VERSION' } }
if ($Build) {
    # A clone has no release.env and no published image to pull, which used to
    # stop the guided installer dead. Build the same Dockerfile the release
    # pipeline builds, tagged uniquely so update still has a real before/after.
    $RepoRoot = (Resolve-Path -LiteralPath (Join-Path $ScriptDir '..\..')).Path
    $DockerfilePath = Join-Path $RepoRoot 'docker/app/Dockerfile'
    if (-not (Test-Path -LiteralPath $DockerfilePath)) {
        Stop-WithError "-Build needs a source checkout; $DockerfilePath is missing."
    }
    if (-not $ImageRepository) { $ImageRepository = 'tinymrp-local' }
    if (-not $Version) {
        $baseVersion = (Get-Content -LiteralPath (Join-Path $RepoRoot 'VERSION') -Raw).Trim()
        if (-not $baseVersion) { Stop-WithError "Could not read $RepoRoot\VERSION." }
        $buildId = ''
        try { $buildId = (& git -C $RepoRoot rev-parse --short=7 HEAD 2>$null) } catch { $buildId = '' }
        if (-not $buildId) { $buildId = (Get-Date).ToUniversalTime().ToString('yyyyMMddHHmmss') }
        $Version = "$baseVersion-src.$($buildId.Trim())"
    }
}
if (-not $ImageRepository -or -not $Version) { Stop-WithError 'This is not a versioned Community bundle. Re-run with -Build to build from source, or pass -ImageRepository and -Version explicitly.' }
if ($Version -notmatch '^v?[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$') { Stop-WithError 'Version must be a Docker-safe semantic version, never latest.' }

# Nothing sits in front of the app in localhost/lan mode, so no X-Forwarded-*
# header can be believed: a client that sends its own would get a private
# rate-limit bucket and a forged address in the audit log. Domain mode puts
# Caddy in front, which overwrites them.
$bindIp = '127.0.0.1'; $domain = ''; $acmeEmail = ''; $origin = "http://localhost:$Port"; $url = $origin; $proxyHops = 0; $internalTls = $false
if ($AccessMode -eq 'lan') {
    if (-not $Address) {
        $detected = Get-NetIPAddress -AddressFamily IPv4 -PrefixOrigin Dhcp -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '169.254.*' } | Select-Object -ExpandProperty IPAddress -First 1
        $Address = Read-Default 'LAN hostname or IP shown to users' $(if ($detected) { $detected } else { '192.168.1.10' })
    }
    $bindIp = '0.0.0.0'; $origin = "http://${Address}:$Port"; $url = $origin
} elseif ($AccessMode -eq 'domain') {
    if ((Test-Port 80) -or (Test-Port 443)) { Stop-WithError 'Domain mode requires free TCP ports 80 and 443.' }
    if (-not $Address) { $Address = Read-Default 'Domain users will type (DNS or hosts file must point here)' 'tinymrp.example.com' }
    $domain = $Address
    if (Test-InternalDomain $domain) {
        # No public CA can issue for a name like this, so Caddy signs it itself.
        # Real HTTPS, but not trusted until the root certificate is distributed.
        $internalTls = $true
        $acmeEmail = $AdminEmail
        Write-Host ""
        Write-Host "NOTE: $domain is an internal-only name, so no public certificate"
        Write-Host "authority can issue for it. Caddy will generate its own certificate"
        Write-Host "instead. TinyMRP works over HTTPS immediately, but until you install"
        Write-Host "Caddy's root certificate on each machine, browsers show ""your"
        Write-Host "connection is not private"" and the SolidWorks add-in refuses to"
        Write-Host "connect. The commands for that are printed at the end. Nothing else"
        Write-Host "changes."
        Write-Host ""
    } else {
        Write-Host ""
        Write-Host "$domain is a public name, so Caddy fetches a real certificate from"
        Write-Host "Let's Encrypt on first start. That needs public DNS already pointing"
        Write-Host "at this machine, and TCP 80 reachable from the internet."
        Write-Host ""
        $acmeEmail = Read-Default 'Email for certificate expiry notices' $AdminEmail
    }
    $origin = "https://$domain"; $url = $origin; $proxyHops = 1
}

New-Item -ItemType Directory -Force -Path $DeliverablesPath | Out-Null
$DeliverablesPath = (Resolve-Path -LiteralPath $DeliverablesPath).Path.Replace('\', '/')
New-Item -ItemType Directory -Force -Path (Join-Path $ScriptDir 'backups') | Out-Null

$lines = [Collections.Generic.List[string]]::new()
Add-EnvValue $lines COMPOSE_PROJECT_NAME 'tinymrp-community'
Add-EnvValue $lines TINYMRP_IMAGE_REPOSITORY $ImageRepository
Add-EnvValue $lines TINYMRP_VERSION $Version
Add-EnvValue $lines ACCESS_MODE $AccessMode
Add-EnvValue $lines APP_BIND_IP $bindIp
Add-EnvValue $lines APP_PORT $Port.ToString()
# TINYMRP_URL is not cosmetic: its scheme is what tells the application whether
# to mark session cookies Secure and to emit upgrade-insecure-requests. Both are
# right over HTTPS and both make a plain-HTTP LAN install impossible to log into,
# so this value and the access mode must never disagree.
Add-EnvValue $lines TINYMRP_URL $url
Add-EnvValue $lines TINYMRP_TRUSTED_PROXY_HOPS $proxyHops.ToString()
Add-EnvValue $lines TINYMRP_ALLOWED_ORIGINS $origin
Add-EnvValue $lines DELIVERABLES_PATH $DeliverablesPath
Add-EnvValue $lines MONGO_DB 'tinymrp'
Add-EnvValue $lines MONGO_ROOT_USER 'tinymrp_root'
Add-EnvValue $lines MONGO_ROOT_PASSWORD (New-HexSecret)
Add-EnvValue $lines MONGO_APP_USER 'tinymrp_app'
Add-EnvValue $lines MONGO_APP_PASSWORD (New-HexSecret)
Add-EnvValue $lines SECRET_KEY (New-HexSecret)
Add-EnvValue $lines SECURITY_PASSWORD_SALT (New-HexSecret)
Add-EnvValue $lines TINYMRP_SEED_ADMIN 'true'
Add-EnvValue $lines TINYMRP_ADMIN_EMAIL $AdminEmail
Add-EnvValue $lines TINYMRP_ADMIN_PASSWORD $plainAdminPassword
Add-EnvValue $lines WEB_CONCURRENCY ''
Add-EnvValue $lines LOG_LEVEL 'INFO'
Add-EnvValue $lines LOG_FORMAT 'text'
Add-EnvValue $lines BACKUP_KEEP_DAYS '14'
Add-EnvValue $lines BACKUP_KEEP_COUNT '8'
Add-EnvValue $lines BACKUP_MAX_TOTAL_GB '10'
Add-EnvValue $lines TINYMRP_DOMAIN $domain
Add-EnvValue $lines ACME_EMAIL $acmeEmail
Add-EnvValue $lines CADDY_BIND_IP '0.0.0.0'
[IO.File]::WriteAllLines($EnvFile, $lines, [Text.UTF8Encoding]::new($false))

try {
    Invoke-DockerCommand compose --env-file $EnvFile -f $ComposeFile config --quiet | Out-Null
    if ($Build) {
        Write-Host "Building ${ImageRepository}:${Version} from $RepoRoot (several minutes on a first build)..."
        Invoke-DockerCommand build -f $DockerfilePath -t "${ImageRepository}:${Version}" $RepoRoot
        # The app tag exists only on this host, so it must never be pulled. But
        # --pull is a stack-wide flag, and mongo, redis and caddy still have to
        # come down from a registry on a machine that has never run this stack.
        # 'never' blocked those too, so every first -Build install on a clean
        # host died with "No such image: mongo:6.0@sha256:...". 'missing' pulls
        # what is absent and leaves the image we just built alone.
        if (-not $env:TINYMRP_INSTALL_PULL) { $env:TINYMRP_INSTALL_PULL = 'missing' }
    }
    $pullMode = if ($env:TINYMRP_INSTALL_PULL) { $env:TINYMRP_INSTALL_PULL } else { 'always' }
    if ($pullMode -notin @('always', 'missing', 'never')) { Stop-WithError 'TINYMRP_INSTALL_PULL must be always, missing, or never.' }
    if ($AccessMode -eq 'domain') {
        Invoke-DockerCommand compose --env-file $EnvFile -f $ComposeFile --profile domain up -d --pull $pullMode --wait
    } else {
        Invoke-DockerCommand compose --env-file $EnvFile -f $ComposeFile up -d --pull $pullMode --wait
    }
    $lines = [Collections.Generic.List[string]](Get-Content -LiteralPath $EnvFile)
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i].StartsWith('TINYMRP_SEED_ADMIN=')) { $lines[$i] = 'TINYMRP_SEED_ADMIN="false"' }
        if ($lines[$i].StartsWith('TINYMRP_ADMIN_PASSWORD=')) { $lines[$i] = 'TINYMRP_ADMIN_PASSWORD=""' }
    }
    [IO.File]::WriteAllLines($EnvFile, $lines, [Text.UTF8Encoding]::new($false))
    Invoke-DockerCommand compose --env-file $EnvFile -f $ComposeFile up -d --no-deps --force-recreate --wait app
    if ($WithDemoData) {
        Write-Host "`nInstalling the evaluation dataset..."
        $demoOutput = Invoke-DockerCommand compose --env-file $EnvFile -f $ComposeFile exec -T app flask --app run.py demo install
    }
} catch {
    try { Invoke-DockerCommand compose --env-file $EnvFile -f $ComposeFile --profile domain logs --tail 100 app mongo redis caddy } catch { Write-Warning $_ }
    throw
}

if ($AccessMode -eq 'lan') {
    # Windows applies a firewall rule only on the profile(s) it is scoped to,
    # and says nothing when none of them are active. A Private-scoped rule on a
    # network Windows has classified Public is inert: the install looks
    # finished and no other machine can connect. Surface it here, because
    # nothing later in the process will.
    $publicProfiles = @(Get-NetConnectionProfile -ErrorAction SilentlyContinue |
        Where-Object { $_.NetworkCategory -eq 'Public' })
    $ruleProfiles = 'Private'
    if ($publicProfiles) {
        Write-Warning ("This network is classified Public on: " +
            (($publicProfiles | ForEach-Object { $_.InterfaceAlias }) -join ', '))
        Write-Host 'A Private-only firewall rule would have no effect there. Either reclassify'
        Write-Host 'the network (recommended, and only if you trust it):'
        Write-Host ('  Set-NetConnectionProfile -InterfaceAlias "' +
            $publicProfiles[0].InterfaceAlias + '" -NetworkCategory Private')
        Write-Host 'or let this installer scope the rule to Public as well.'
        $widen = Read-Host 'Scope the rule to Public networks too? (y/N)'
        if ($widen -match '^(y|yes)$') { $ruleProfiles = 'Private,Public' }
    }
    $answer = Read-Host "Add a Windows Firewall rule for TCP $Port on $ruleProfiles networks? (y/N)"
    if ($answer -match '^(y|yes)$') {
        try {
            New-NetFirewallRule -DisplayName "TinyMRP Community ($Port)" -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -Profile $ruleProfiles | Out-Null
            Write-Host "Firewall rule added for $ruleProfiles networks."
        } catch { Write-Warning "Firewall rule was not added (an elevated terminal may be required): $_" }
    } else {
        Write-Host 'No firewall rule added. Docker Desktop publishes ports through its own'
        Write-Host 'rules, so this often still works; verify from another machine with:'
        Write-Host "  Test-NetConnection <this-host> -Port $Port"
        Write-Host 'and diagnose with deploy\windows\check_lan_access.ps1 if it fails.'
    }
}

Write-Host "`nTinyMRP Community is ready at $url"
Write-Host "Administrator: $AdminEmail"
if ($WithDemoData -and $demoOutput) {
    Write-Host "`nEvaluation dataset installed. These demo passwords are shown ONCE:"
    $demoOutput | ForEach-Object { Write-Host $_ }
    Write-Host "`nRemove them before this instance holds real data:"
    Write-Host "  docker compose --env-file `"$EnvFile`" -f `"$ComposeFile`" exec -T app flask --app run.py demo remove --disable"
}
if ($internalTls) {
    Write-Host "`n$domain uses a certificate from Caddy's own authority. Export the"
    Write-Host 'root certificate once:'
    Write-Host ''
    Write-Host "  docker compose --env-file `"$EnvFile`" -f `"$ComposeFile`" ``"
    Write-Host '    cp caddy:/data/caddy/pki/authorities/local/root.crt .\tinymrp-root-ca.crt'
    Write-Host ''
    Write-Host 'Then install tinymrp-root-ca.crt as a trusted root on every machine'
    Write-Host 'that opens TinyMRP or runs the SolidWorks add-in:'
    Write-Host ''
    Write-Host '  Windows  certutil -addstore -f Root tinymrp-root-ca.crt   (as Administrator)'
    Write-Host '  Ubuntu   sudo cp tinymrp-root-ca.crt /usr/local/share/ca-certificates/ && sudo update-ca-certificates'
    Write-Host '  Firefox  Settings > Privacy & Security > Certificates > View Certificates > Authorities > Import'
    Write-Host ''
    Write-Host "Every client must also resolve $domain to this machine, through your"
    Write-Host 'internal DNS or a hosts-file entry.'
}

Write-Host "`nUse .\tinymrp.ps1 status|logs|backup|update for operations."
Write-Host 'To change the address, port or access mode later, run:'
Write-Host '  .\tinymrp.ps1 reconfigure'
