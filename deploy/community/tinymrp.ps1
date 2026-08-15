<#
.SYNOPSIS
    Operate an installed Community stack: start, stop, status, logs, backup, restore, update, uninstall.
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'stop', 'status', 'logs', 'update', 'backup', 'restore', 'uninstall')]
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
if ($Argument -and $Argument.StartsWith('--')) { $Argument = '' }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile = Join-Path $ScriptDir '.env'
$ComposeFile = Join-Path $ScriptDir 'compose.yaml'
$BackupRoot = Join-Path $ScriptDir 'backups'
$MinimumDumpBytes = 1024L

function Stop-WithError([string]$Message) {
    throw $Message
}

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

function Update-Stack([string]$Target) {
    Assert-Installed; Assert-Runtime
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
    default { Stop-WithError 'Usage: .\tinymrp.ps1 {start|stop|status|logs|backup|restore|update|uninstall}' }
}
