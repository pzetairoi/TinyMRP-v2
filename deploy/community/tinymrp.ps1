<#
.SYNOPSIS
    Operate an installed Community stack: start, stop, status, logs, backup, restore, update, uninstall.
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'stop', 'status', 'logs', 'reconfigure', 'set-certificate', 'update', 'backup', 'restore', 'uninstall')]
    [string]$Command,
    [Parameter(Position = 1)]
    [string]$Argument,
    [Parameter(Position = 2)]
    [string]$Option,
    [switch]$IncludeDeliverables,
    [switch]$DeleteData,
    [switch]$Yes,
    # Accept the Linux flag spelling too. Everything is documented with both
    # forms, and people copy commands between the two platforms; without this,
    # `.	inymrp.ps1 uninstall --delete-data --yes` dies inside PowerShell's
    # parameter binder with "A parameter cannot be found that matches parameter
    # name 'delete-data'", which says nothing about TinyMRP.
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = 'Stop'

# Normalise the GNU-style flags into the switches the body already uses, so the
# two platforms accept the same command lines.
$extraArguments = @()
foreach ($candidate in @($Argument, $Option) + @($Rest)) {
    if ($candidate) { $extraArguments += $candidate.ToString().ToLowerInvariant() }
}
if ($extraArguments -contains '--include-deliverables') { $IncludeDeliverables = $true }
if ($extraArguments -contains '--delete-data') { $DeleteData = $true }
if ($extraArguments -contains '--yes') { $Yes = $true }
# A positional argument that was really a flag must not be mistaken for a
# backup directory or a version tag.
if ($Argument -and $Argument.StartsWith('--') -and $Command -ne 'set-certificate') { $Argument = '' }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile = Join-Path $ScriptDir '.env'
$ComposeFile = Join-Path $ScriptDir 'compose.yaml'
$BackupRoot = Join-Path $ScriptDir 'backups'
$MinimumDumpBytes = 1024L

function Stop-WithError([string]$Message) {
    throw $Message
}

. (Join-Path $ScriptDir 'lib-tls.ps1')

function Assert-Installed {
    if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
        Stop-WithError 'No installation found. Run install.cmd or install.ps1 first.'
    }
}

function Assert-Runtime {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Stop-WithError 'Docker Desktop is required.'
    }
    & cmd.exe /d /c "docker info >nul 2>nul"
    if ($LASTEXITCODE -ne 0) { Stop-WithError 'Docker Desktop is not running.' }
    & cmd.exe /d /c "docker compose version >nul 2>nul"
    if ($LASTEXITCODE -ne 0) { Stop-WithError 'Docker Compose v2 is required.' }
}

function Invoke-DockerCommand {
    $DockerArguments = @($args)
    $savedPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & docker @DockerArguments
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedPreference
    }
    if ($exitCode -ne 0) { Stop-WithError "docker failed with exit code $exitCode." }
    return $output
}

function Invoke-Compose {
    Invoke-DockerCommand compose --env-file $EnvFile -f $ComposeFile @args
}

function Get-EnvValue([string]$Name) {
    $line = Get-Content -LiteralPath $EnvFile | Where-Object { $_ -like "$Name=*" } | Select-Object -First 1
    if ($null -eq $line) { return '' }
    $value = $line.Substring($Name.Length + 1)
    if ($value.Length -ge 2 -and $value[0] -eq '"' -and $value[$value.Length - 1] -eq '"') {
        $value = $value.Substring(1, $value.Length - 2)
    }
    return $value.Replace('$$', '$').Replace('\"', '"').Replace('\\', '\')
}

function Set-EnvValue([string]$Name, [string]$Value) {
    if ($Value.Contains("`r") -or $Value.Contains("`n")) { Stop-WithError "$Name cannot contain a newline." }
    $escaped = $Value.Replace('\', '\\').Replace('"', '\"').Replace('$', '$$')
    $replacement = "$Name=`"$escaped`""
    $lines = [Collections.Generic.List[string]](Get-Content -LiteralPath $EnvFile)
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i].StartsWith("$Name=")) { $lines[$i] = $replacement; $found = $true; break }
    }
    if (-not $found) { $lines.Add($replacement) }
    [IO.File]::WriteAllLines($EnvFile, $lines, [Text.UTF8Encoding]::new($false))
}

function Wait-App([int]$Attempts = 40) {
    $container = (Invoke-DockerCommand compose --env-file $EnvFile -f $ComposeFile ps -q app).Trim()
    if (-not $container) { return $false }
    while ($Attempts -gt 0) {
        $state = (Invoke-DockerCommand inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $container).Trim()
        if ($state -eq 'healthy') { return $true }
        if ($state -in @('unhealthy', 'exited', 'dead')) { return $false }
        Start-Sleep -Seconds 3
        $Attempts--
    }
    return $false
}

function Start-Stack {
    if ((Get-EnvValue 'ACCESS_MODE') -eq 'domain') {
        Invoke-Compose --profile domain up -d --wait
    } else {
        Invoke-Compose up -d --wait
    }
}

function Read-Default([string]$Prompt, [string]$Default) {
    $value = Read-Host "$Prompt [$Default]"
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value.Trim()
}

function Test-Port([int]$Number) {
    return $null -ne (Get-NetTCPConnection -State Listen -LocalPort $Number -ErrorAction SilentlyContinue | Select-Object -First 1)
}

# Defined once, in lib-tls.ps1, so this script and the installer cannot drift.
function Test-InternalDomain([string]$Domain) { return Test-TlsInternalDomain $Domain }

# Eight keys in .env describe one decision: how browsers reach this server.
# They have to agree, and the failure when they do not is a silent login loop
# rather than an error. Editing .env by hand means getting all eight right by
# hand; this asks the three questions the installer asked and derives the rest.
function Invoke-Reconfigure {
    $oldMode = Get-EnvValue 'ACCESS_MODE'; if (-not $oldMode) { $oldMode = 'localhost' }
    $oldPort = Get-EnvValue 'APP_PORT'; if (-not $oldPort) { $oldPort = '5000' }
    Write-Host "Current address: $(Get-EnvValue 'TINYMRP_URL') (access mode: $oldMode)"
    Write-Host @'

  localhost  only this machine, http://localhost:<port>
  lan        any machine on the network, http://<ip-or-name>:<port>, plain HTTP
  domain     https://<domain> with TLS terminated by Caddy; needs 80 and 443

'@
    $mode = Read-Default 'Access mode (localhost/lan/domain)' $oldMode
    if ($mode -notin @('localhost', 'lan', 'domain')) { Stop-WithError 'Access mode must be localhost, lan, or domain.' }

    $bindIp = '127.0.0.1'; $domain = ''; $acmeEmail = ''; $proxyHops = 0
    if ($mode -eq 'domain') {
        $newPort = Read-Default 'Internal loopback port for diagnostics (users reach 443)' $oldPort
    } else {
        $newPort = Read-Default 'TinyMRP port' $oldPort
    }
    $parsedPort = 0
    if (-not [int]::TryParse($newPort, [ref]$parsedPort) -or $parsedPort -lt 1 -or $parsedPort -gt 65535) {
        Stop-WithError 'Port must be between 1 and 65535.'
    }

    switch ($mode) {
        'localhost' { $origin = "http://localhost:$parsedPort" }
        'lan' {
            $bindIp = '0.0.0.0'
            $detected = Get-NetIPAddress -AddressFamily IPv4 -PrefixOrigin Dhcp -ErrorAction SilentlyContinue |
                Where-Object { $_.IPAddress -notlike '169.254.*' } | Select-Object -ExpandProperty IPAddress -First 1
            $lanHost = Read-Default 'LAN hostname or IP shown to users' $(if ($detected) { $detected } else { '192.168.1.10' })
            if (-not $lanHost) { Stop-WithError 'A LAN hostname or IP is required.' }
            $origin = "http://${lanHost}:$parsedPort"
        }
        'domain' {
            $domain = Read-Default 'Domain users will type' (Get-EnvValue 'TINYMRP_DOMAIN')
            if (-not $domain) { Stop-WithError 'A domain is required in domain mode.' }
            $acmeEmail = Read-Default 'Email for certificate notices' (Get-EnvValue 'ACME_EMAIL')
            $origin = "https://$domain"; $proxyHops = 1
        }
    }
    $url = $origin

    Write-Host "`nNew address will be: $url"
    if ((Read-Default 'Apply and restart? (yes/no)' 'yes') -ne 'yes') { Stop-WithError 'Nothing was changed.' }

    if ($mode -eq 'domain' -and $oldMode -ne 'domain') {
        if ((Test-Port 80) -or (Test-Port 443)) { Stop-WithError 'Domain mode requires free TCP ports 80 and 443. Nothing was changed.' }
    }
    # Stop only what has to stop. Leaving domain mode has to remove Caddy; the
    # database has no reason to bounce because an address changed.
    if ($mode -ne 'domain' -and $oldMode -eq 'domain') {
        try { Invoke-Compose --profile domain rm -sf caddy | Out-Null } catch { }
    }

    Set-EnvValue 'ACCESS_MODE' $mode
    Set-EnvValue 'APP_BIND_IP' $bindIp
    Set-EnvValue 'APP_PORT' $parsedPort.ToString()
    Set-EnvValue 'TINYMRP_URL' $url
    Set-EnvValue 'TINYMRP_TRUSTED_PROXY_HOPS' $proxyHops.ToString()
    Set-EnvValue 'TINYMRP_ALLOWED_ORIGINS' $origin
    Set-EnvValue 'TINYMRP_DOMAIN' $domain
    Set-EnvValue 'ACME_EMAIL' $acmeEmail

    Start-Stack
    if (-not (Wait-App)) { Stop-WithError "Reconfigured to $url but TinyMRP did not become healthy; see .\tinymrp.ps1 logs." }
    Write-Host "`nTinyMRP is now at $url"
    if ($mode -eq 'domain' -and (Test-InternalDomain $domain)) {
        Write-Host "`n$domain is an internal-only name, so Caddy signs it with its own"
        Write-Host 'authority. Export the root certificate and trust it on every client:'
        Write-Host ''
        Write-Host "  docker compose --env-file `"$EnvFile`" -f `"$ComposeFile`" ``"
        Write-Host '    cp caddy:/data/caddy/pki/authorities/local/root.crt .\tinymrp-root-ca.crt'
        Write-Host ''
        Write-Host '  Windows  certutil -addstore -f Root tinymrp-root-ca.crt   (as Administrator)'
    }
}

function Set-Certificate([string]$CertPath, [string]$KeyPath) {
    Assert-Installed; Assert-Runtime
    $mode = Get-EnvValue 'ACCESS_MODE'
    $domain = Get-EnvValue 'TINYMRP_DOMAIN'
    if ($mode -ne 'domain') { Stop-WithError "Certificates only apply in domain mode; this instance is in '$mode' mode. Switch first with: .	inymrp.ps1 reconfigure" }
    if (-not $domain) { Stop-WithError 'TINYMRP_DOMAIN is empty. Run .	inymrp.ps1 reconfigure first.' }

    if ($CertPath -eq '--automatic' -or $CertPath -eq '-Automatic') {
        Install-TlsAutomatic $ScriptDir
        Set-EnvValue 'TINYMRP_TLS_MODE' 'automatic'
        Write-Host "Switched $domain back to an automatically obtained certificate."
        if (Test-TlsInternalDomain $domain) {
            Write-Host 'It is an internal-only name, so Caddy will sign it with its own authority'
            Write-Host 'and clients will distrust it until you install that root certificate.'
        }
    } else {
        if (-not $CertPath -or -not $KeyPath) {
            Stop-WithError "Usage: .	inymrp.ps1 set-certificate <certificate-file> <private-key-file>`n       .	inymrp.ps1 set-certificate --automatic"
        }
        Write-Host "Checking the certificate against $domain..."
        $days = Test-TlsPair $CertPath $KeyPath $domain
        Show-TlsCert (Read-TlsCertificate $CertPath)
        # Back up first: a bad swap on a live instance is otherwise unrecoverable
        # without going back to IT for the previous files.
        $dir = Get-TlsCertsDir $ScriptDir
        $existing = Join-Path $dir 'server.crt'
        if (Test-Path -LiteralPath $existing) {
            $backup = Join-Path $dir ("previous-" + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ'))
            New-Item -ItemType Directory -Force -Path $backup | Out-Null
            Copy-Item -LiteralPath $existing -Destination $backup -Force -ErrorAction SilentlyContinue
            Copy-Item -LiteralPath (Join-Path $dir 'server.key') -Destination $backup -Force -ErrorAction SilentlyContinue
            Write-Host "Previous certificate kept in $backup"
        }
        Install-TlsProvided $ScriptDir $CertPath $KeyPath
        Set-EnvValue 'TINYMRP_TLS_MODE' 'provided'
        if ($days -lt 30) { Write-Host "WARNING: this certificate expires in $days day(s)." }
    }

    Write-Host 'Restarting the proxy...'
    try {
        Invoke-Compose --profile domain up -d --no-deps --force-recreate --wait caddy | Out-Null
    } catch {
        Stop-WithError "Caddy did not come back up. Inspect: .	inymrp.ps1 logs`nThe previous certificate files, if any, are still in $(Get-TlsCertsDir $ScriptDir)."
    }

    # Proving it: a mismatched key would have stopped Caddy, and comparing the
    # served certificate with the file is what confirms the swap took effect.
    if ($CertPath -ne '--automatic' -and $CertPath -ne '-Automatic') {
        $onDisk = Read-TlsCertificate $CertPath
        Start-Sleep -Seconds 2
        $served = $null
        try {
            $client = New-Object System.Net.Sockets.TcpClient('127.0.0.1', 443)
            $ssl = New-Object System.Net.Security.SslStream($client.GetStream(), $false, { $true })
            $ssl.AuthenticateAsClient($domain)
            $served = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 $ssl.RemoteCertificate
            $ssl.Dispose(); $client.Close()
        } catch { $served = $null }
        if ($served -and $served.Thumbprint -eq $onDisk.Thumbprint) {
            Write-Host "`nVerified: $domain is now serving your certificate."
        } else {
            Write-Warning 'Could not confirm the served certificate matches the file. Check with: bash ./check-install.sh'
        }
    } else {
        Write-Host "`n$domain is serving an automatically obtained certificate again."
    }
}

function Get-GzipContentSize([string]$Path) {
    $input = [IO.File]::OpenRead($Path)
    try {
        $gzip = [IO.Compression.GzipStream]::new($input, [IO.Compression.CompressionMode]::Decompress)
        try {
            $buffer = New-Object byte[] 65536
            [long]$total = 0
            while (($read = $gzip.Read($buffer, 0, $buffer.Length)) -gt 0) { $total += $read }
            return $total
        } finally { $gzip.Dispose() }
    } finally { $input.Dispose() }
}

function Assert-Backup([string]$Directory) {
    $archive = Join-Path $Directory 'mongo.archive.gz'
    $checksums = Join-Path $Directory 'checksums.sha256'
    if (-not (Test-Path -LiteralPath $archive -PathType Leaf) -or -not (Test-Path -LiteralPath $checksums -PathType Leaf)) {
        Stop-WithError 'Backup is incomplete.'
    }
    foreach ($line in Get-Content -LiteralPath $checksums) {
        if ($line -notmatch '^([0-9a-fA-F]{64})  (.+)$') { Stop-WithError 'Invalid checksum manifest.' }
        $file = Join-Path $Directory $Matches[2]
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { Stop-WithError "Missing backup file: $($Matches[2])" }
        $actual = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $Matches[1].ToLowerInvariant()) { Stop-WithError "Checksum failed: $($Matches[2])" }
    }
    $size = Get-GzipContentSize $archive
    if ($size -lt $MinimumDumpBytes) { Stop-WithError "Mongo archive contains only $size uncompressed bytes; refusing an empty backup." }
    return $size
}

function Remove-ExpiredBackups {
    $keepDays = [int](Get-EnvValue 'BACKUP_KEEP_DAYS'); if ($keepDays -lt 0) { $keepDays = 14 }
    $keepCount = [int](Get-EnvValue 'BACKUP_KEEP_COUNT'); if ($keepCount -lt 1) { $keepCount = 8 }
    $maxGb = [int](Get-EnvValue 'BACKUP_MAX_TOTAL_GB'); if ($maxGb -lt 1) { $maxGb = 10 }
    $maxBytes = [long]$maxGb * 1GB
    while ($true) {
        $items = @(Get-ChildItem -LiteralPath $BackupRoot -Directory | Where-Object Name -Match '^20.*Z$' | Sort-Object Name -Descending)
        if ($items.Count -le 1) { break }
        $newest = $items[0].FullName
        $total = ($items | ForEach-Object { (Get-ChildItem -LiteralPath $_.FullName -File -Recurse | Measure-Object Length -Sum).Sum } | Measure-Object -Sum).Sum
        $candidate = $items | Select-Object -Skip 1 | Where-Object { $keepDays -gt 0 -and $_.LastWriteTimeUtc -lt [DateTime]::UtcNow.AddDays(-$keepDays) } | Select-Object -Last 1
        if (-not $candidate -and ($items.Count -gt $keepCount -or $total -gt $maxBytes)) { $candidate = $items[-1] }
        if (-not $candidate -or $candidate.FullName -eq $newest) { break }
        $resolvedRoot = [IO.Path]::GetFullPath($BackupRoot).TrimEnd('\') + '\'
        $resolvedTarget = [IO.Path]::GetFullPath($candidate.FullName)
        if (-not $resolvedTarget.StartsWith($resolvedRoot, [StringComparison]::OrdinalIgnoreCase)) { Stop-WithError 'Unsafe backup prune target.' }
        Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
        Write-Host "Pruned backup $($candidate.Name) under retention policy."
    }
}

function Backup-Stack([bool]$WithDeliverables) {
    Assert-Installed; Assert-Runtime
    New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
    $stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
    $partial = Join-Path $BackupRoot ".$stamp.partial"
    $target = Join-Path $BackupRoot $stamp
    New-Item -ItemType Directory -Path $partial | Out-Null
    $container = (Invoke-DockerCommand compose --env-file $EnvFile -f $ComposeFile ps -q mongo).Trim()
    if (-not $container) { Stop-WithError 'Mongo is not running.' }
    $remoteArchive = "/tmp/tinymrp-$stamp.archive.gz"
    try {
        Invoke-DockerCommand exec $container sh -c "exec mongodump --quiet --username `"`$MONGO_INITDB_ROOT_USERNAME`" --password `"`$MONGO_INITDB_ROOT_PASSWORD`" --authenticationDatabase admin --db `"`$MONGO_INITDB_DATABASE`" --archive=$remoteArchive --gzip" | Out-Null
        Invoke-DockerCommand cp "${container}:$remoteArchive" (Join-Path $partial 'mongo.archive.gz') | Out-Null
    } finally { try { Invoke-DockerCommand exec $container rm -f $remoteArchive | Out-Null } catch { Write-Warning $_ } }
    Copy-Item -LiteralPath $EnvFile -Destination (Join-Path $partial 'config.env')
    if ($WithDeliverables) {
        $image = "$(Get-EnvValue 'TINYMRP_IMAGE_REPOSITORY'):$(Get-EnvValue 'TINYMRP_VERSION')"
        $source = Get-EnvValue 'DELIVERABLES_PATH'
        Invoke-DockerCommand run --rm --entrypoint tar --mount "type=bind,source=$source,target=/source,readonly" --mount "type=bind,source=$partial,target=/backup" $image -czf /backup/deliverables.tar.gz -C /source . | Out-Null
    }
    $size = Get-GzipContentSize (Join-Path $partial 'mongo.archive.gz')
    if ($size -lt $MinimumDumpBytes) { Stop-WithError "Mongo archive contains only $size uncompressed bytes; refusing an empty backup." }
    @(
        "created_utc=$stamp",
        "image=$(Get-EnvValue 'TINYMRP_IMAGE_REPOSITORY'):$(Get-EnvValue 'TINYMRP_VERSION')",
        "mongo_uncompressed_bytes=$size",
        "deliverables_included=$($WithDeliverables.ToString().ToLowerInvariant())"
    ) | Set-Content -LiteralPath (Join-Path $partial 'metadata.txt') -Encoding Ascii
    $files = @('mongo.archive.gz', 'config.env', 'metadata.txt'); if ($WithDeliverables) { $files += 'deliverables.tar.gz' }
    $manifest = foreach ($file in $files) { "$(Get-FileHash -LiteralPath (Join-Path $partial $file) -Algorithm SHA256 | Select-Object -ExpandProperty Hash | ForEach-Object ToLowerInvariant)  $file" }
    [IO.File]::WriteAllLines((Join-Path $partial 'checksums.sha256'), $manifest, [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $partial -Destination $target
    Remove-ExpiredBackups
    Write-Host "Verified backup: $target ($size uncompressed Mongo bytes)"
}

function Restore-Stack([string]$Source, [bool]$WithDeliverables, [bool]$Confirmed) {
    Assert-Installed; Assert-Runtime
    if (-not $Source) { Stop-WithError 'Usage: .\tinymrp.ps1 restore BACKUP_DIR [-IncludeDeliverables] [-Yes]' }
    $Source = (Resolve-Path -LiteralPath $Source).Path
    [void](Assert-Backup $Source)
    if (-not $Confirmed) {
        $answer = Read-Host "Replace the TinyMRP database from $Source? Type RESTORE"
        if ($answer -ne 'RESTORE') { Stop-WithError 'Restore cancelled.' }
    }
    Invoke-Compose up -d --wait mongo
    Invoke-Compose stop app | Out-Null
    $container = (Invoke-DockerCommand compose --env-file $EnvFile -f $ComposeFile ps -q mongo).Trim()
    $remoteArchive = '/tmp/tinymrp-restore.archive.gz'
    Invoke-DockerCommand cp (Join-Path $Source 'mongo.archive.gz') "${container}:$remoteArchive" | Out-Null
    try {
        Invoke-DockerCommand exec $container sh -c "exec mongosh --quiet --username `"`$MONGO_INITDB_ROOT_USERNAME`" --password `"`$MONGO_INITDB_ROOT_PASSWORD`" --authenticationDatabase admin /opt/tinymrp/mongo-clear-data.js" | Out-Null
        Invoke-DockerCommand exec $container sh -c "exec mongorestore --quiet --drop --username `"`$MONGO_INITDB_ROOT_USERNAME`" --password `"`$MONGO_INITDB_ROOT_PASSWORD`" --authenticationDatabase admin --nsInclude `"`$MONGO_INITDB_DATABASE.*`" --archive=$remoteArchive --gzip" | Out-Null
    } finally { try { Invoke-DockerCommand exec $container rm -f $remoteArchive | Out-Null } catch { Write-Warning $_ } }
    if ($WithDeliverables) {
        $archive = Join-Path $Source 'deliverables.tar.gz'
        if (-not (Test-Path -LiteralPath $archive)) { Stop-WithError 'This backup has no deliverables archive.' }
        $image = "$(Get-EnvValue 'TINYMRP_IMAGE_REPOSITORY'):$(Get-EnvValue 'TINYMRP_VERSION')"
        $destination = Get-EnvValue 'DELIVERABLES_PATH'
        $listing = Invoke-DockerCommand run --rm --entrypoint tar --mount "type=bind,source=$archive,target=/backup.tar.gz,readonly" $image -tzf /backup.tar.gz
        if ($listing | Where-Object { $_ -match '(^/|(^|/)\.\.(/|$))' }) { Stop-WithError 'Deliverables archive contains an unsafe path.' }
        Invoke-DockerCommand run --rm --entrypoint tar --mount "type=bind,source=$archive,target=/backup.tar.gz,readonly" --mount "type=bind,source=$destination,target=/destination" $image -xzf /backup.tar.gz -C /destination | Out-Null
    }
    Start-Stack
    if (-not (Wait-App)) { Stop-WithError 'Restore completed but TinyMRP did not become healthy.' }
    Write-Host 'Restore verified; TinyMRP is healthy. config.env was retained as evidence and was not applied.'
}

# An install made with `install.ps1 -Build` runs an image that exists only on
# this host, tagged <VERSION>-src.<sha>. There is nothing to pull, so the
# registry path below cannot serve it.
function Test-SourceInstall {
    $repo = Get-EnvValue 'TINYMRP_IMAGE_REPOSITORY'
    $version = Get-EnvValue 'TINYMRP_VERSION'
    return ($repo -eq 'tinymrp-local' -or $version -like '*-src.*')
}

function Update-FromSource {
    Assert-Installed; Assert-Runtime
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Stop-WithError 'git is required to update from source.' }
    $repoRoot = (Resolve-Path -LiteralPath (Join-Path $ScriptDir '..\..') -ErrorAction SilentlyContinue).Path
    $dockerfile = if ($repoRoot) { Join-Path $repoRoot 'docker\app\Dockerfile' } else { '' }
    if (-not $repoRoot -or -not (Test-Path -LiteralPath $dockerfile)) {
        Stop-WithError 'Source updates need a git checkout. This looks like an extracted release bundle, so use: .\tinymrp.ps1 update vMAJOR.MINOR.PATCH'
    }
    & git -C $repoRoot rev-parse --git-dir 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { Stop-WithError "$repoRoot is not a git repository, so there is nothing to pull." }

    # A rebuild bakes the working tree into the image; doing that silently with
    # uncommitted edits produces an image nobody can reproduce later.
    $dirty = & git -C $repoRoot status --porcelain --untracked-files=no
    if ($dirty) {
        $dirty | ForEach-Object { Write-Host $_ }
        Stop-WithError "Uncommitted changes in $repoRoot. Commit or stash them first, so the image you run matches a known commit."
    }
    $branch = (& git -C $repoRoot rev-parse --abbrev-ref HEAD).Trim()
    if ($branch -eq 'HEAD') { Stop-WithError "The checkout is on a detached HEAD. Run: git -C $repoRoot checkout main" }
    $upstream = (& git -C $repoRoot rev-parse --abbrev-ref '@{upstream}' 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $upstream) { Stop-WithError "Branch $branch has no upstream, so there is nothing to pull from." }

    Write-Host "Fetching $upstream..."
    & git -C $repoRoot fetch --quiet --prune
    if ($LASTEXITCODE -ne 0) { Stop-WithError 'git fetch failed. Check network access to the remote.' }
    & git -C $repoRoot merge --ff-only '@{upstream}' 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { Stop-WithError "$branch cannot be fast-forwarded to $upstream, so this checkout has diverged. Resolve it by hand: git -C $repoRoot status" }

    $baseVersion = (Get-Content -LiteralPath (Join-Path $repoRoot 'VERSION') -Raw).Trim()
    if (-not $baseVersion) { Stop-WithError "Could not read $repoRoot\VERSION." }
    $sha = (& git -C $repoRoot rev-parse --short=7 HEAD).Trim()
    $newVersion = "$baseVersion-src.$sha"
    $old = Get-EnvValue 'TINYMRP_VERSION'
    $imageRepository = Get-EnvValue 'TINYMRP_IMAGE_REPOSITORY'
    if (-not $imageRepository) { $imageRepository = 'tinymrp-local' }

    & docker image inspect "${imageRepository}:${newVersion}" 2>$null | Out-Null
    if ($newVersion -eq $old -and $LASTEXITCODE -eq 0) {
        Write-Host "Already up to date: $sha is the newest commit on $branch, and its image is built."
        return
    }

    Write-Host "Updating from $old to $newVersion..."
    Backup-Stack $false
    $backup = Get-ChildItem -LiteralPath $BackupRoot -Directory | Sort-Object Name -Descending | Select-Object -First 1
    Write-Host "Building ${imageRepository}:${newVersion} (several minutes; later builds reuse the cache)..."
    Invoke-DockerCommand build -f $dockerfile -t "${imageRepository}:${newVersion}" $repoRoot

    Set-EnvValue 'TINYMRP_VERSION' $newVersion
    try {
        Invoke-Compose up -d --no-deps --force-recreate app
        if (-not (Wait-App)) { Stop-WithError 'Replacement app did not become healthy.' }
        if ((Get-EnvValue 'ACCESS_MODE') -eq 'domain') { Start-Stack }
        Write-Host "`nUpdated TinyMRP from $old to $newVersion."
        Write-Host "Pre-update backup: $($backup.FullName)"
        Write-Host "The previous image ${imageRepository}:${old} was kept, so a rollback needs no rebuild."
    } catch {
        Write-Warning "Update failed; rolling back to $old."
        Set-EnvValue 'TINYMRP_VERSION' $old
        Invoke-Compose up -d --no-deps --force-recreate app
        if (-not (Wait-App)) { Stop-WithError "Automatic rollback also failed. Your data backup is $($backup.FullName)" }
        Stop-WithError "Update to $newVersion failed; app rolled back to $old. Data backup is $($backup.FullName)"
    }
}

function Update-Stack([string]$Target) {
    Assert-Installed; Assert-Runtime
    if ($Target -eq '--from-source' -or $Target -eq '-FromSource') { Update-FromSource; return }
    if (-not $Target) {
        if (Test-SourceInstall) { Update-FromSource; return }
        Stop-WithError @'
Usage: .\tinymrp.ps1 update vMAJOR.MINOR.PATCH
This instance runs a published release image, so an update needs the version to move to.
An instance installed from a git checkout with -Build updates with no argument.
'@
    }
    if (Test-SourceInstall) {
        Stop-WithError @"
This instance was installed from a git checkout (image $(Get-EnvValue 'TINYMRP_IMAGE_REPOSITORY'):$(Get-EnvValue 'TINYMRP_VERSION')).
Its image exists only on this host and was never published, so there is no $Target to pull.
Update it from source instead:  .\tinymrp.ps1 update
"@
    }
    if ($Target -notmatch '^v?[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$') { Stop-WithError 'Usage: .\tinymrp.ps1 update vMAJOR.MINOR.PATCH' }
    $old = Get-EnvValue 'TINYMRP_VERSION'
    if ($Target -eq $old) { Stop-WithError "TinyMRP is already configured for $Target." }
    Backup-Stack $false
    $backup = Get-ChildItem -LiteralPath $BackupRoot -Directory | Sort-Object Name -Descending | Select-Object -First 1
    Set-EnvValue 'TINYMRP_VERSION' $Target
    try {
        Invoke-Compose pull app
        Invoke-Compose up -d --no-deps --force-recreate app
        if (-not (Wait-App)) { Stop-WithError 'Replacement app did not become healthy.' }
        Write-Host "Updated TinyMRP from $old to $Target. Pre-update backup: $($backup.FullName)"
    } catch {
        Write-Warning "Update failed; rolling the app image back to $old."
        Set-EnvValue 'TINYMRP_VERSION' $old
        try { Invoke-Compose pull app } catch { Write-Warning $_ }
        Invoke-Compose up -d --no-deps --force-recreate app
        if (-not (Wait-App)) { Stop-WithError "Automatic rollback also failed. Data backup is $($backup.FullName)" }
        Stop-WithError "Update to $Target failed; app rolled back to $old. Data backup is $($backup.FullName)"
    }
}

Assert-Installed
switch ($Command) {
    'start' { Assert-Runtime; Start-Stack; Write-Host "TinyMRP started: $(Get-EnvValue 'TINYMRP_URL')" }
    'stop' { Assert-Runtime; Invoke-Compose --profile domain stop }
    'status' { Assert-Runtime; Invoke-Compose --profile domain ps }
    'reconfigure' { Assert-Runtime; Invoke-Reconfigure }
    'set-certificate' { Set-Certificate $Argument $Option }
    'logs' { Assert-Runtime; Invoke-Compose --profile domain logs --tail $(if ($Argument) { $Argument } else { '200' }) -f app mongo redis caddy }
    'backup' { Backup-Stack ([bool]$IncludeDeliverables) }
    'restore' { Restore-Stack $Argument ([bool]$IncludeDeliverables) ([bool]$Yes) }
    'update' { Update-Stack $Argument }
    'uninstall' {
        Assert-Runtime
        if ($DeleteData) {
            if (-not ($Yes -or $Option -eq '--yes')) { Stop-WithError 'Destructive use requires: .\tinymrp.ps1 uninstall -DeleteData -Yes' }
            Invoke-Compose --profile domain down -v --remove-orphans
            Write-Host 'Docker-managed Mongo/Caddy volumes deleted. Configuration, backups, and deliverables were preserved.'
        } else {
            Invoke-Compose --profile domain down --remove-orphans
            Write-Host 'Application removed. Mongo data, configuration, backups, and deliverables were preserved.'
        }
    }
    default { Stop-WithError 'Usage: .\tinymrp.ps1 {start|stop|status|logs|reconfigure|set-certificate|backup|restore|update|uninstall}' }
}
