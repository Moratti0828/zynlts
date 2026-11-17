param([string]$SshAlias = 'gpu-server', [int]$LocalPort = 8877, [switch]$Background)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw '找不到支持连接中继的 Python；请设置本机 Python 路径。' }
$taskWlan = Get-NetIPAddress -InterfaceAlias 'WLAN' -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '169.254.*' } | Select-Object -First 1
if (-not $taskWlan) { throw 'WLAN没有有效IPv4地址；请先连接可访问服务器的校园网络。' }
$taskRelay = Join-Path $env:TEMP 'reading-bench-current-ssh-relay.py'
Copy-Item -LiteralPath (Join-Path $taskRoot 'deploy/ssh_wlan_relay.py') -Destination $taskRelay
$taskProxy = 'ProxyCommand=' + $taskPython.Replace('\','/') + ' ' + $taskRelay.Replace('\','/') + ' %h %p ' + $taskWlan.IPAddress + ' ' + $taskWlan.InterfaceIndex
$taskArgs = @('-N','-L',("127.0.0.1:{0}:127.0.0.1:8787" -f $LocalPort),'-o','ExitOnForwardFailure=yes','-o','ServerAliveInterval=30','-o','ServerAliveCountMax=3','-o','BatchMode=yes','-o','ConnectTimeout=8')
Write-Output ("服务器平台入口：http://127.0.0.1:{0}" -f $LocalPort)
if ($Background) {
    $taskState = Join-Path $taskRoot 'var'
    New-Item -ItemType Directory -Path $taskState -Force | Out-Null
    $taskProcess = Start-Process -FilePath 'ssh.exe' -ArgumentList ($taskArgs + @('-o',('"' + $taskProxy + '"'),$SshAlias)) -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskState 'tunnel.stdout.log') -RedirectStandardError (Join-Path $taskState 'tunnel.stderr.log') -PassThru
    $taskProcess.Id | Set-Content -LiteralPath (Join-Path $taskState 'tunnel.pid')
    Write-Output ("隧道PID：{0}；仅在完成演示后终止该进程即可关闭隧道。" -f $taskProcess.Id)
} else {
    Write-Output '请在演示期间保持此终端窗口打开；关闭窗口将断开服务器连接。'
    & ssh.exe @taskArgs -o $taskProxy $SshAlias
}
