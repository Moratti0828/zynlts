param(
    [switch]$Local,
    [ValidateRange(0, 65535)][int]$Port = 0,
    [string]$SshAlias = 'gpu-server',
    [ValidateRange(5, 120)][int]$WaitSeconds = 40,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskState = Join-Path $taskRoot 'var'
$taskPort = if ($Port -gt 0) { $Port } elseif ($Local) { 8787 } else { 8877 }
$taskBaseUrl = 'http://127.0.0.1:' + $taskPort
$taskDemoUrl = $taskBaseUrl + '/#demo'
$taskHeaders = @{}
if ($env:READING_BENCH_TOKEN) { $taskHeaders['Authorization'] = 'Bearer ' + $env:READING_BENCH_TOKEN }

function Get-DemoHttp {
    param([string]$Url, [int]$TimeoutSeconds = 4)
    try {
        $taskValue = Invoke-RestMethod -Uri $Url -Method Get -Headers $taskHeaders -TimeoutSec $TimeoutSeconds
        return [pscustomobject]@{ Ok = $true; Code = 200; Data = $taskValue }
    } catch {
        $taskCode = 0
        if ($_.Exception.Response) {
            try { $taskCode = [int]$_.Exception.Response.StatusCode } catch { $taskCode = 0 }
        }
        return [pscustomobject]@{ Ok = $false; Code = $taskCode; Data = $null }
    }
}

function Test-DemoPort {
    param([int]$PortNumber)
    $taskClient = New-Object System.Net.Sockets.TcpClient
    try {
        $taskConnect = $taskClient.BeginConnect('127.0.0.1', $PortNumber, $null, $null)
        if (-not $taskConnect.AsyncWaitHandle.WaitOne(400)) { return $false }
        $taskClient.EndConnect($taskConnect)
        return $true
    } catch { return $false }
    finally { $taskClient.Dispose() }
}

function Wait-DemoHealth {
    param([string]$BaseUrl, [int]$Seconds)
    $taskDeadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    do {
        $taskHealth = Get-DemoHttp ($BaseUrl + '/api/health') 2
        if ($taskHealth.Ok -and $taskHealth.Data.status -eq 'ok') { return $true }
        if ($taskHealth.Code -eq 401) { return $false }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $taskDeadline)
    return $false
}

function Start-DemoLocalOllama {
    $taskOllama = Get-DemoHttp 'http://127.0.0.1:11434/api/tags' 3
    if ($taskOllama.Ok) { return }
    if (Test-DemoPort 11434) {
        Write-Warning '本机11434端口已有服务，但没有返回Ollama模型列表；不会停止该服务。请在模型管理中检查服务地址。'
        return
    }
    $taskCommand = Get-Command ollama.exe -ErrorAction SilentlyContinue
    if (-not $taskCommand) {
        Write-Warning '未找到本机Ollama。平台仍可使用已配置的其他推理接口；不会自动下载模型。'
        return
    }
    $taskPreviousHost = $env:OLLAMA_HOST
    try {
        $env:OLLAMA_HOST = '127.0.0.1:11434'
        $taskProcess = Start-Process -FilePath $taskCommand.Source -ArgumentList 'serve' -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskState 'demo-ollama.stdout.log') -RedirectStandardError (Join-Path $taskState 'demo-ollama.stderr.log') -PassThru
        $taskProcess.Id | Set-Content -LiteralPath (Join-Path $taskState 'demo-ollama.pid')
    } finally { $env:OLLAMA_HOST = $taskPreviousHost }
    $taskDeadline = [DateTime]::UtcNow.AddSeconds(12)
    do {
        if ((Get-DemoHttp 'http://127.0.0.1:11434/api/tags' 2).Ok) { return }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $taskDeadline)
    Write-Warning '本机模型服务尚未就绪。查看var/demo-ollama.stderr.log，平台连接检查仍会报告实际状态。'
}

function Start-DemoLocalApp {
    Start-DemoLocalOllama
    $taskShell = Join-Path $PSHOME 'powershell.exe'
    if (-not (Test-Path -LiteralPath $taskShell)) { $taskShell = (Get-Command powershell.exe).Source }
    $taskPreviousHost = $env:READING_BENCH_HOST
    $taskPreviousLabel = $env:READING_BENCH_DEPLOYMENT_LABEL
    try {
        $env:READING_BENCH_HOST = '127.0.0.1'
        $env:READING_BENCH_DEPLOYMENT_LABEL = '本机 · Ollama'
        $taskArguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + (Join-Path $taskRoot 'start.ps1') + '"'), '-Port', [string]$taskPort)
        $taskProcess = Start-Process -FilePath $taskShell -ArgumentList $taskArguments -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskState 'demo-app.stdout.log') -RedirectStandardError (Join-Path $taskState 'demo-app.stderr.log') -PassThru
        $taskProcess.Id | Set-Content -LiteralPath (Join-Path $taskState 'demo-app.pid')
    } finally {
        $env:READING_BENCH_HOST = $taskPreviousHost
        $env:READING_BENCH_DEPLOYMENT_LABEL = $taskPreviousLabel
    }
}

# Startup is intentionally separate from model generation. No POST requests,
# weight downloads, global routes, or process termination occur in this file.
Write-Output ('现场演示入口：' + $taskDemoUrl)
$taskHealth = Get-DemoHttp ($taskBaseUrl + '/api/health')
if (-not ($taskHealth.Ok -and $taskHealth.Data.status -eq 'ok')) {
    if ($taskHealth.Code -eq 401) {
        throw '平台需要访问令牌。请在当前终端设置READING_BENCH_TOKEN，或在网页右上角输入令牌；脚本不会记录令牌。'
    }
    if (Test-DemoPort $taskPort) {
        throw ('端口' + $taskPort + '已有监听，但没有返回健康的平台。不会停止占用进程；请确认服务，或使用-Port指定空闲端口。')
    }
    if ($CheckOnly) { throw '平台尚未连接。去掉-CheckOnly以启动连接；服务器不可达时可明确使用-Local。' }
    New-Item -ItemType Directory -Path $taskState -Force | Out-Null
    if ($Local) {
        Write-Output '正在后台启动本机平台和已有Ollama服务，不会下载模型。'
        Start-DemoLocalApp
    } else {
        Write-Output ('正在后台建立服务器隧道：' + $SshAlias + '。仅使用当前WLAN连接，不修改全局路由。')
        & (Join-Path $taskRoot 'connect-server.ps1') -SshAlias $SshAlias -LocalPort $taskPort -Background
    }
    if (-not (Wait-DemoHealth $taskBaseUrl $WaitSeconds)) {
        $taskLog = if ($Local) { 'var/demo-app.stderr.log' } else { 'var/tunnel.stderr.log' }
        throw ('平台在等待时间内尚未连接。查看' + $taskLog + '；服务器模式请检查校园WLAN和SSH密钥；本机演示使用 .\launch-demo.ps1 -Local。后台进程未被强行终止。')
    }
} else {
    Write-Output '已复用当前健康平台，没有重复启动服务。'
}
$taskStatus = Get-DemoHttp ($taskBaseUrl + '/api/demo/status') 60
if (-not $taskStatus.Ok) {
    if ($taskStatus.Code -eq 401) { throw '演示接口需要访问令牌；在网页右上角输入，或在终端设置READING_BENCH_TOKEN后重试。' }
    if ($taskStatus.Code -eq 404) { throw '平台已连接，但尚未包含现场演示接口。请更新并重启本项目平台；不会自动停止已有服务。' }
    throw '平台已连接，但现场演示接口暂未响应。页面仍可打开，请点击重新检查连接并查看模型管理。'
}
if ($taskStatus.Data.status -eq 'busy') {
    Write-Output '已有实验正在执行。打开页面恢复查看进度，完成后再创建新的现场演示。'
    return
}
if (-not $taskStatus.Data.ready) {
    Write-Warning '平台已连接，但尚未通过演示就绪检查。请在页面查看具体模型、题库或连接诊断。'
    if ($taskStatus.Data.problems) { $taskStatus.Data.problems | ForEach-Object { Write-Warning ([string]$_) } }
    throw '演示尚未就绪；没有发起模型推理，也没有伪造成功结果。'
}
Write-Output '演示就绪：打开上述地址，选模型与题目，再点击开始。检查连接没有调用模型。'
Write-Output '首次运行可能需要加载权重；后台平台/SSH隧道会继续运行，可关闭这个启动终端。'
