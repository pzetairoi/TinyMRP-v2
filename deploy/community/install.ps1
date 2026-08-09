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
    [string]$Version
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
if (-not $AccessMode) { $AccessMode = Read-Default 'Access mode (localhost/lan/domain)' 'localhost' }
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
if (-not $ImageRepository -or -not $Version) { Stop-WithError 'This is not a versioned Community bundle. Pass -ImageRepository and -Version explicitly.' }
if ($Version -notmatch '^v?[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$') { Stop-WithError 'Version must be a Docker-safe semantic version, never latest.' }

$bindIp = '127.0.0.1'; $domain = ''; $acmeEmail = ''; $origin = "http://localhost:$Port"; $url = $origin
if ($AccessMode -eq 'lan') {
    if (-not $Address) {
        $detected = Get-NetIPAddress -AddressFamily IPv4 -PrefixOrigin Dhcp -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '169.254.*' } | Select-Object -ExpandProperty IPAddress -First 1
        $Address = Read-Default 'LAN hostname or IP shown to users' $(if ($detected) { $detected } else { '192.168.1.10' })
    }
    $bindIp = '0.0.0.0'; $origin = "http://${Address}:$Port"; $url = $origin
} elseif ($AccessMode -eq 'domain') {
    if ((Test-Port 80) -or (Test-Port 443)) { Stop-WithError 'Domain mode requires free TCP ports 80 and 443.' }
    if (-not $Address) { $Address = Read-Default 'Public domain (DNS must point here)' 'tinymrp.example.com' }
    $domain = $Address; $acmeEmail = Read-Default 'ACME certificate email' $AdminEmail
    $origin = "https://$domain"; $url = $origin
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
Add-EnvValue $lines TINYMRP_URL $url
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
} catch {
    try { Invoke-DockerCommand compose --env-file $EnvFile -f $ComposeFile --profile domain logs --tail 100 app mongo redis caddy } catch { Write-Warning $_ }
    throw
}

if ($AccessMode -eq 'lan') {
    $answer = Read-Host "Add a Windows Firewall rule for TCP $Port on Private networks only? (y/N)"
    if ($answer -match '^(y|yes)$') {
        try {
            New-NetFirewallRule -DisplayName "TinyMRP Community ($Port)" -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -Profile Private | Out-Null
            Write-Host 'Private-network firewall rule added.'
        } catch { Write-Warning "Firewall rule was not added (an elevated terminal may be required): $_" }
    }
}

Write-Host "`nTinyMRP Community is ready at $url"
Write-Host "Administrator: $AdminEmail"
Write-Host "Use .\tinymrp.ps1 status|logs|backup|update for operations."
