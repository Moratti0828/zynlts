# Offline launcher checks: no network, process starts, or inference.
$ErrorActionPreference = 'Stop'
$taskSource = Join-Path (Split-Path -Parent $PSScriptRoot) 'launch-demo.ps1'
$taskTokens = $null
$taskParseErrors = $null
$taskAst = [System.Management.Automation.Language.Parser]::ParseFile($taskSource, [ref]$taskTokens, [ref]$taskParseErrors)
if ($taskParseErrors.Count) { throw ('Launcher syntax error: ' + $taskParseErrors[0].Message) }
$taskFunctions = $taskAst.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $false)
foreach ($taskFunction in $taskFunctions) { . ([scriptblock]::Create($taskFunction.Extent.Text)) }
$taskHeaders = @{ Authorization = 'Bearer offline-test-value' }
$script:TaskRequest = $null
$script:TaskFailRequest = $false
function Invoke-RestMethod {
    param($Uri, $Method, $Headers, $TimeoutSec)
    $script:TaskRequest = @{ Uri = $Uri; Method = $Method; Headers = $Headers; Timeout = $TimeoutSec }
    if ($script:TaskFailRequest) { throw 'offline simulated connection failure' }
    return [pscustomobject]@{ status = 'ok' }
}
function Assert-Demo {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}
$taskReply = Get-DemoHttp 'http://offline.invalid/api/health' 3
Assert-Demo ($taskReply.Ok -and $taskReply.Code -eq 200) 'Healthy response must be available.'
Assert-Demo ($script:TaskRequest.Method -eq 'Get') 'Readiness must only issue GET.'
Assert-Demo ($script:TaskRequest.Headers.Authorization -eq 'Bearer offline-test-value') 'Deployment token must be forwarded in the header.'
$script:TaskFailRequest = $true
$taskReply = Get-DemoHttp 'http://offline.invalid/api/health' 3
Assert-Demo (-not $taskReply.Ok -and $taskReply.Code -eq 0) 'Connection failure must remain unavailable.'
$script:TaskFetchCount = 0
function Get-DemoHttp {
    param($Url, $TimeoutSeconds)
    $script:TaskFetchCount++
    return [pscustomobject]@{ Ok = $true; Code = 200; Data = [pscustomobject]@{ status = 'ok' } }
}
Assert-Demo (Wait-DemoHealth 'http://offline.invalid' 5) 'Healthy platform should return immediately.'
Assert-Demo ($script:TaskFetchCount -eq 1) 'Healthy platform must not be redundantly polled.'
function Get-DemoHttp {
    param($Url, $TimeoutSeconds)
    return [pscustomobject]@{ Ok = $false; Code = 401; Data = $null }
}
Assert-Demo (-not (Wait-DemoHealth 'http://offline.invalid' 5)) 'Authentication failure must not report ready.'
function Start-Process { throw 'No process may start in this offline test.' }
function Get-DemoHttp {
    param($Url, $TimeoutSeconds)
    return [pscustomobject]@{ Ok = $true; Code = 200; Data = [pscustomobject]@{ models = @() } }
}
Start-DemoLocalOllama
function Get-DemoHttp {
    param($Url, $TimeoutSeconds)
    return [pscustomobject]@{ Ok = $false; Code = 0; Data = $null }
}
function Test-DemoPort { param($PortNumber) return $true }
Start-DemoLocalOllama -WarningAction SilentlyContinue
$taskBusyEvidence = [pscustomobject]@{ Count = 0 }
function Invoke-RestMethod {
    param($Uri, $Method, $Headers, $TimeoutSec)
    $taskBusyEvidence.Count++
    if ($Uri -like '*/api/health') { return [pscustomobject]@{ status = 'ok' } }
    if ($Uri -like '*/api/demo/status') { return [pscustomobject]@{ status = 'busy'; ready = $false; problems = @('Existing run') } }
    throw 'Unexpected request; this test must not reach a model endpoint.'
}
& $taskSource -Local -CheckOnly
Assert-Demo ($taskBusyEvidence.Count -eq 2) 'Busy platform should be readable without another start or inference.'
Write-Output 'PASS: parser; GET-only and token header; connection failure; immediate reuse; authentication failure; existing Ollama reuse; occupied model port; busy platform recovery.'
