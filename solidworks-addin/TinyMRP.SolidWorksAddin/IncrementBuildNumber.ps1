param(
    [Parameter(Mandatory = $true)]
    [string]$Path,
    [string]$Increment = "false"
)

$fullPath = [IO.Path]::GetFullPath($Path)
$directory = [IO.Path]::GetDirectoryName($fullPath)
[IO.Directory]::CreateDirectory($directory) | Out-Null
$shouldIncrement = [string]::Equals($Increment, "true", [StringComparison]::OrdinalIgnoreCase)

for ($attempt = 0; $attempt -lt 20; $attempt++) {
    $stream = $null
    try {
        $stream = [IO.File]::Open($fullPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
        $bytes = New-Object byte[] $stream.Length
        [void]$stream.Read($bytes, 0, $bytes.Length)
        $current = 0
        [void][int]::TryParse([Text.Encoding]::UTF8.GetString($bytes).Trim(), [ref]$current)
        $buildNumber = if ($shouldIncrement) { [Math]::Max(1, $current + 1) } else { [Math]::Max(1, $current) }

        if ($shouldIncrement -or $stream.Length -eq 0) {
            $output = [Text.Encoding]::UTF8.GetBytes($buildNumber.ToString() + [Environment]::NewLine)
            $stream.Position = 0
            $stream.SetLength(0)
            $stream.Write($output, 0, $output.Length)
            $stream.Flush($true)
        }

        Write-Output $buildNumber
        exit 0
    }
    catch [IO.IOException] {
        Start-Sleep -Milliseconds 50
    }
    finally {
        if ($null -ne $stream) {
            $stream.Dispose()
        }
    }
}

throw "Could not lock build number file: $fullPath"
