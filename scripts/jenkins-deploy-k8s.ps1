$ErrorActionPreference = 'Stop'

foreach ($name in @('APP_SECRET_KEY', 'DATABASE_URI', 'IMAGE_NAME', 'IMAGE_TAG', 'WORKSPACE')) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
        throw "Required Jenkins environment variable $name is missing."
    }
}

if ($env:APP_SECRET_KEY.Length -lt 32) {
    throw 'The configured application secret must be at least 32 characters.'
}

if ($env:DATABASE_URI -notmatch '^postgresql(\+psycopg2)?://') {
    throw 'The configured database URI must use PostgreSQL.'
}

$kubectl = (Get-Command kubectl.exe -ErrorAction Stop).Source
$workspace = $env:WORKSPACE
$tempDirectory = Join-Path $env:TEMP "jenkins-forensics-$([guid]::NewGuid().ToString('N'))"
$secretManifest = Join-Path $tempDirectory 'secret.yaml'
$deploymentManifest = Join-Path $tempDirectory 'deployment.yaml'

function Invoke-Kubectl {
    param([string[]]$Arguments)

    & $kubectl @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "kubectl $($Arguments -join ' ') failed with exit code $LASTEXITCODE."
    }
}

try {
    New-Item -ItemType Directory -Path $tempDirectory | Out-Null

    $acl = Get-Acl -LiteralPath $tempDirectory
    $acl.SetAccessRuleProtection($true, $false)
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
    $rule = [System.Security.AccessControl.FileSystemAccessRule]::new(
        $identity,
        [System.Security.AccessControl.FileSystemRights]::FullControl,
        [System.Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit',
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
    $acl.SetAccessRule($rule)
    Set-Acl -LiteralPath $tempDirectory -AclObject $acl

    Invoke-Kubectl -Arguments @('apply', '-f', (Join-Path $workspace 'k8s\namespace.yaml'))
    Invoke-Kubectl -Arguments @('apply', '-f', (Join-Path $workspace 'k8s\configmap.yaml'))
    Invoke-Kubectl -Arguments @('apply', '-f', (Join-Path $workspace 'k8s\pvc.yaml'))

    $secretKey = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($env:APP_SECRET_KEY))
    $databaseUri = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($env:DATABASE_URI))
    $secretYaml = @"
apiVersion: v1
kind: Secret
metadata:
  name: forensics-secrets
  namespace: digital-forensics
type: Opaque
data:
  SECRET_KEY: "$secretKey"
  DATABASE_URI: "$databaseUri"
"@
    [IO.File]::WriteAllText($secretManifest, $secretYaml, [Text.UTF8Encoding]::new($false))
    Invoke-Kubectl -Arguments @('apply', '-f', $secretManifest)

    $sourceDeployment = Join-Path $workspace 'k8s\deployment.yaml'
    $deploymentYaml = [IO.File]::ReadAllText($sourceDeployment)
    $imagePattern = '(?m)^([ \t]*image:[ \t]*).+$'
    if ([regex]::Matches($deploymentYaml, $imagePattern).Count -ne 1) {
        throw 'Expected exactly one image entry in k8s/deployment.yaml.'
    }
    $image = "$($env:IMAGE_NAME):$($env:IMAGE_TAG)"
    $deploymentYaml = [regex]::Replace($deploymentYaml, $imagePattern, ('$1' + $image), 1)
    [IO.File]::WriteAllText($deploymentManifest, $deploymentYaml, [Text.UTF8Encoding]::new($false))
    Invoke-Kubectl -Arguments @('apply', '-f', $deploymentManifest)
    Invoke-Kubectl -Arguments @('apply', '-f', (Join-Path $workspace 'k8s\service.yaml'))
    Invoke-Kubectl -Arguments @('apply', '-f', (Join-Path $workspace 'k8s\ingress.yaml'))
    Invoke-Kubectl -Arguments @('rollout', 'status', 'deployment/forensics-app', '--namespace', 'digital-forensics', '--timeout=180s')
}
finally {
    if (Test-Path -LiteralPath $tempDirectory) {
        Remove-Item -LiteralPath $tempDirectory -Recurse -Force
    }
}
