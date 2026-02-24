[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$AppRoot,
    [Parameter(Mandatory = $true)]
    [string]$EnvFile,
    [string]$ListenHost = "127.0.0.1",
    [int]$Port = 8000,
    [int]$Threads = 8,
    [int]$ConnectionLimit = 400,
    [int]$ChannelTimeout = 120
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $AppRoot)) {
    throw "AppRoot not found: $AppRoot"
}

if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Env file not found: $EnvFile"
}

$waitressExe = Join-Path $AppRoot ".venv\Scripts\waitress-serve.exe"
if (-not (Test-Path -LiteralPath $waitressExe)) {
    throw "waitress-serve not found: $waitressExe (install dependencies in .venv first)"
}

$env:ENV_FILE = $EnvFile
$env:PYTHONUNBUFFERED = "1"

Set-Location -LiteralPath $AppRoot

$args = @(
    "--host=$ListenHost",
    "--port=$Port",
    "--threads=$Threads",
    "--connection-limit=$ConnectionLimit",
    "--channel-timeout=$ChannelTimeout",
    "app.wsgi:app"
)

& $waitressExe @args
exit $LASTEXITCODE
