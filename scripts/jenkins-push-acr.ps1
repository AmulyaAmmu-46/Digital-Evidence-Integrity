$ErrorActionPreference = 'Stop'

foreach ($name in @('ACR_NAME', 'ACR_USERNAME', 'ACR_PASSWORD')) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
        throw "Required Jenkins environment variable $name is missing."
    }
}

if ($env:ACR_USERNAME -match '[\s"]') {
    throw 'The configured ACR username contains unsupported whitespace or quotes.'
}

$docker = (Get-Command docker.exe -ErrorAction Stop).Source
$registry = "$($env:ACR_NAME).azurecr.io"
$startInfo = New-Object System.Diagnostics.ProcessStartInfo
$startInfo.FileName = $docker
$startInfo.Arguments = "login $registry --username $($env:ACR_USERNAME) --password-stdin"
$startInfo.UseShellExecute = $false
$startInfo.RedirectStandardInput = $true

$process = New-Object System.Diagnostics.Process
$process.StartInfo = $startInfo

try {
    if (-not $process.Start()) {
        throw 'Could not start Docker to authenticate with Azure Container Registry.'
    }

    $process.StandardInput.WriteLine($env:ACR_PASSWORD)
    $process.StandardInput.Close()
    $process.WaitForExit()

    if ($process.ExitCode -ne 0) {
        throw "Docker registry login failed with exit code $($process.ExitCode)."
    }
}
finally {
    $process.Dispose()
}
