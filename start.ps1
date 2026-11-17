param([int]$Port = 8787)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:READING_BENCH_PORT = "$Port"
$bundledPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$projectPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (Test-Path -LiteralPath $projectPython) { & $projectPython -X utf8 -m backend.server }
elseif (Test-Path -LiteralPath $bundledPython) { & $bundledPython -X utf8 -m backend.server }
elseif (Get-Command py -ErrorAction SilentlyContinue) { py -3 -X utf8 -m backend.server }
else { python -X utf8 -m backend.server }
