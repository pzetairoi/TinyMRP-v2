# Certificate handling shared by install.ps1 and tinymrp.ps1.
# The PowerShell counterpart of lib-tls.sh; see that file for why TLS mode
# "provided" exists. Dot-sourced, never executed.
#
# Windows has no openssl by default, so the checks here use .NET rather than
# shelling out. That covers the four mistakes people actually make - handing
# over the CA root, a certificate for the wrong hostname, one with no SAN, and
# an expired one. The certificate/key pairing is proved differently from the
# shell version: Caddy is started and the served certificate is compared with
# the file, which catches a mismatched key just as reliably.

function Get-TlsCertsDir([string]$ScriptDir) { Join-Path $ScriptDir 'certs' }

function Test-TlsInternalDomain([string]$Domain) {
    $d = $Domain.ToLowerInvariant()
    foreach ($suffix in @('.local', '.localdomain', '.localhost', '.internal', '.intranet',
                          '.lan', '.home.arpa', '.test', '.invalid', '.example',
                          '.example.com', '.example.org', '.example.net')) {
        if ($d.EndsWith($suffix)) { return $true }
    }
    return (-not $d.Contains('.'))
}

function Read-TlsCertificate([string]$Path) {
    try {
        return New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 $Path
    } catch {
        return $null
    }
}

# The SAN extension formats its labels in the OS display language, so the label
# text cannot be matched. Everything after each '=' is the value regardless of
# language, which is what we compare.
function Get-TlsCertNames($Cert) {
    $ext = $Cert.Extensions | Where-Object { $_.Oid.Value -eq '2.5.29.17' }
    if (-not $ext) { return @() }
    $names = @()
    foreach ($part in ($ext.Format($false) -split ',')) {
        $idx = $part.IndexOf('=')
        if ($idx -ge 0) { $names += $part.Substring($idx + 1).Trim() }
    }
    return $names
}

function Test-TlsCertCoversDomain($Cert, [string]$Domain) {
    $d = $Domain.ToLowerInvariant()
    foreach ($name in (Get-TlsCertNames $Cert)) {
        $n = $name.ToLowerInvariant()
        if ($n -eq $d) { return $true }
        if ($n.StartsWith('*.') -and $d.Contains('.')) {
            if ($n.Substring(2) -eq $d.Substring($d.IndexOf('.') + 1)) { return $true }
        }
    }
    return $false
}

function Test-TlsCertIsAuthority($Cert) {
    $ext = $Cert.Extensions | Where-Object { $_.Oid.Value -eq '2.5.29.19' }
    if (-not $ext) { return $false }
    try {
        $bc = [System.Security.Cryptography.X509Certificates.X509BasicConstraintsExtension]$ext
        return $bc.CertificateAuthority
    } catch { return $false }
}

function Get-TlsCertDaysRemaining($Cert) {
    return [int][math]::Floor(($Cert.NotAfter - (Get-Date)).TotalDays)
}

# Refuse everything Caddy would choke on later. Returns days remaining.
function Test-TlsPair([string]$CertPath, [string]$KeyPath, [string]$Domain) {
    if (-not (Test-Path -LiteralPath $CertPath)) { Stop-WithError "Certificate file not found: $CertPath" }
    if (-not (Test-Path -LiteralPath $KeyPath)) { Stop-WithError "Private key file not found: $KeyPath" }

    $cert = Read-TlsCertificate $CertPath
    if (-not $cert) {
        Stop-WithError @"
$CertPath is not a readable PEM certificate. It should begin with -----BEGIN CERTIFICATE-----.
If your CA gave you a .pfx or .p12, export the two PEM files from it first.
"@
    }

    $keyText = Get-Content -LiteralPath $KeyPath -Raw
    if ($keyText -match 'ENCRYPTED') {
        Stop-WithError "$KeyPath is passphrase-protected. Caddy runs unattended and cannot be prompted. Ask for an unencrypted key."
    }
    if ($keyText -notmatch '-----BEGIN [A-Z ]*PRIVATE KEY-----') {
        Stop-WithError "$KeyPath does not look like a PEM private key. It should begin with -----BEGIN PRIVATE KEY----- or -----BEGIN RSA PRIVATE KEY-----."
    }

    if (Test-TlsCertIsAuthority $cert) {
        Stop-WithError @"
$CertPath is a certificate authority certificate, not a server certificate.
This is the CA that signs certificates; it is the file you install on client
machines so they trust the server. What Caddy needs here is the certificate
your CA issued FOR $Domain, together with its private key.
"@
    }

    $names = Get-TlsCertNames $cert
    if ($names.Count -eq 0) {
        Stop-WithError @"
$CertPath has no Subject Alternative Name.
Browsers and the SolidWorks add-in have ignored the Common Name for years, so a
certificate without a SAN is rejected by every client. Ask your CA to reissue it
with  DNS:$Domain  in the SAN.
"@
    }
    if (-not (Test-TlsCertCoversDomain $cert $Domain)) {
        Stop-WithError @"
$CertPath is not valid for $Domain.
It covers: $($names -join ', ')
Either reissue it with DNS:$Domain in the SAN, or install with the domain it actually covers.
"@
    }

    $days = Get-TlsCertDaysRemaining $cert
    if ($days -le 0) { Stop-WithError "$CertPath expired $([math]::Abs($days)) day(s) ago. Ask for a current one." }
    return $days
}

function Show-TlsCert($Cert) {
    Write-Host "  Subject : $($Cert.Subject)"
    Write-Host "  Issuer  : $($Cert.Issuer)"
    Write-Host "  Valid   : $(Get-TlsCertDaysRemaining $Cert) day(s) remaining"
    Write-Host "  Names   : $((Get-TlsCertNames $Cert) -join ', ')"
}

function Install-TlsProvided([string]$ScriptDir, [string]$CertPath, [string]$KeyPath) {
    $dir = Get-TlsCertsDir $ScriptDir
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Copy-Item -LiteralPath $CertPath -Destination (Join-Path $dir 'server.crt') -Force
    Copy-Item -LiteralPath $KeyPath -Destination (Join-Path $dir 'server.key') -Force
    # Caddy reads these paths inside its own container, not on the host.
    [IO.File]::WriteAllText((Join-Path $dir 'tls.caddy'),
        "tls /etc/caddy/certs/server.crt /etc/caddy/certs/server.key`n",
        [Text.UTF8Encoding]::new($false))
    # Keep the key off other local accounts; Docker still reads it as the daemon.
    try {
        $acl = Get-Acl (Join-Path $dir 'server.key')
        $acl.SetAccessRuleProtection($true, $false)
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
            [Security.Principal.WindowsIdentity]::GetCurrent().Name, 'FullControl', 'Allow')
        $acl.SetAccessRule($rule)
        Set-Acl -Path (Join-Path $dir 'server.key') -AclObject $acl
    } catch { Write-Warning "Could not tighten permissions on server.key: $($_.Exception.Message)" }
}

function Install-TlsAutomatic([string]$ScriptDir) {
    $dir = Get-TlsCertsDir $ScriptDir
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    foreach ($f in @('tls.caddy', 'server.crt', 'server.key')) {
        $p = Join-Path $dir $f
        if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force }
    }
}
