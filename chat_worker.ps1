# Chat mode: the Claude chat acts as the AI. No API key. Keep this window open.
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
$Root = $PSScriptRoot
$RT   = Join-Path $Root '_runtime'
$py   = Join-Path $RT 'venv\Scripts\python.exe'
if (-not (Test-Path $py)) { Write-Host 'Setup has not finished. Run 1_setup.bat first.'; exit 1 }
$env:PATH = "$(Join-Path $RT 'venv\Scripts');$(Join-Path $RT 'ffmpeg\bin');$(Join-Path $RT 'node');$env:PATH"
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $RT 'ms-playwright'
$env:PYTHONUTF8 = '1'; $env:PYTHONIOENCODING = 'utf-8'; $env:PYTHONUNBUFFERED = '1'
$host.UI.RawUI.WindowTitle = 'CRV PDF - chat mode (keep open)'
Set-Location $Root
& $py chat_worker.py
