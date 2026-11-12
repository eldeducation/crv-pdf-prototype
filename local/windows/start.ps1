# Start the local app (loopback 127.0.0.1 only). Close this window or press Ctrl+C to stop.
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path  # project folder (this script lives in local\windows)
$RT   = Join-Path $Root '_runtime'
$py   = Join-Path $RT 'venv\Scripts\python.exe'
if (-not (Test-Path $py)) { Write-Host 'Setup has not finished. Run 1_setup.bat first.'; exit 1 }

$env:PATH = "$(Join-Path $RT 'venv\Scripts');$(Join-Path $RT 'ffmpeg\bin');$(Join-Path $RT 'node');$env:PATH"
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $RT 'ms-playwright'
$env:PYTHONUTF8 = '1'; $env:PYTHONIOENCODING = 'utf-8'; $env:PYTHONUNBUFFERED = '1'

$record = Join-Path $Root 'server.local.json'
$before = if (Test-Path $record) { (Get-Item $record).LastWriteTimeUtc } else { [datetime]::MinValue }
$proc = Start-Process -FilePath $py -ArgumentList @('server.py', '--reuse-address') -WorkingDirectory $Root -NoNewWindow -PassThru
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    if ($proc.HasExited) { Write-Host "Server exited (code $($proc.ExitCode))."; exit 1 }
    if ((Test-Path $record) -and (Get-Item $record).LastWriteTimeUtc -gt $before) {
        $url = (Get-Content $record -Raw -Encoding UTF8 | ConvertFrom-Json).url
        Write-Host ''
        Write-Host "Open: $url"
        Start-Process $url
        break
    }
}
Wait-Process -Id $proc.Id
