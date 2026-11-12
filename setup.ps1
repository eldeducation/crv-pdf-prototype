# crv-pdf-prototype local setup (no administrator rights needed)
# Everything goes into .\_runtime next to this script. Nothing is installed system-wide,
# no API key is used, and nothing is published or pushed.
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}

$Root = $PSScriptRoot
$RT   = Join-Path $Root '_runtime'
$DL   = Join-Path $RT 'downloads'
$Log  = Join-Path $RT 'setup-log.txt'
New-Item -ItemType Directory -Force -Path $RT, $DL | Out-Null
"==== setup started $(Get-Date -Format s) ====" | Out-File -FilePath $Log -Encoding utf8

function Log([string]$msg) {
    Write-Host $msg
    Add-Content -Path $Log -Value $msg -Encoding utf8
}
function Run([string]$exe, [string[]]$arguments) {
    Log ">> $exe $($arguments -join ' ')"
    & $exe @arguments 2>&1 | ForEach-Object { $line = "$_"; Write-Host $line; Add-Content -Path $Log -Value $line -Encoding utf8 }
    $code = $LASTEXITCODE
    Log "   (exit $code)"
    return $code
}
function Fetch([string]$url, [string]$out) {
    if (Test-Path $out) { Log "already downloaded: $out"; return }
    Log "download: $url"
    for ($i = 1; $i -le 3; $i++) {
        try { Invoke-WebRequest -Uri $url -OutFile "$out.part" -UseBasicParsing; Move-Item "$out.part" $out -Force; return }
        catch { Log "  attempt $i failed: $($_.Exception.Message)"; Start-Sleep -Seconds 3 }
    }
    throw "download failed: $url"
}
function Unzip([string]$zip, [string]$dest) {
    if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    $tar = Join-Path $env:SystemRoot 'System32\tar.exe'
    if (Test-Path $tar) { & $tar -xf $zip -C $dest; if ($LASTEXITCODE -eq 0) { return } }
    Expand-Archive -Path $zip -DestinationPath $dest -Force
}

$results = [ordered]@{}
try {
    # ---------- 1. uv (Python manager) ----------
    $uv = Join-Path $RT 'uv\uv.exe'
    if (-not (Test-Path $uv)) {
        $zip = Join-Path $DL 'uv.zip'
        Fetch 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip' $zip
        Unzip $zip (Join-Path $RT 'uv')
    }
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $RT 'python'
    $env:UV_CACHE_DIR          = Join-Path $RT 'uv-cache'
    $env:UV_LINK_MODE          = 'copy'
    Run $uv @('--version') | Out-Null

    # ---------- 2. Python 3.12 + venv ----------
    $venv = Join-Path $RT 'venv'
    $py   = Join-Path $venv 'Scripts\python.exe'
    if (-not (Test-Path $py)) {
        Run $uv @('python', 'install', '3.12') | Out-Null
        Run $uv @('venv', $venv, '--python', '3.12', '--python-preference', 'only-managed') | Out-Null
    }
    if (-not (Test-Path $py)) { throw 'Python venv was not created' }

    # ---------- 3. Python packages (torch CPU, Whisper, crv, yt-dlp, Pillow, pypdf) ----------
    $c = Run $uv @('pip', 'install', '--python', $py, 'torch', '--index-url', 'https://download.pytorch.org/whl/cpu')
    if ($c -ne 0) { throw 'torch install failed' }
    $c = Run $uv @('pip', 'install', '--python', $py, '-r', (Join-Path $Root 'requirements.txt'))
    if ($c -ne 0) { throw 'requirements install failed' }

    # ---------- 4. FFmpeg ----------
    $ffbin = Join-Path $RT 'ffmpeg\bin'
    if (-not (Test-Path (Join-Path $ffbin 'ffmpeg.exe'))) {
        $zip = Join-Path $DL 'ffmpeg.zip'
        Fetch 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip' $zip
        $tmp = Join-Path $DL 'ffmpeg-x'
        Unzip $zip $tmp
        $inner = Get-ChildItem $tmp -Directory | Select-Object -First 1
        if (Test-Path (Join-Path $RT 'ffmpeg')) { Remove-Item (Join-Path $RT 'ffmpeg') -Recurse -Force }
        Move-Item $inner.FullName (Join-Path $RT 'ffmpeg')
        Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ---------- 5. Node.js 24 (portable zip) ----------
    $nodeDir = Join-Path $RT 'node'
    $node = Join-Path $nodeDir 'node.exe'
    if (-not (Test-Path $node)) {
        $index = Invoke-RestMethod -Uri 'https://nodejs.org/dist/index.json' -UseBasicParsing
        $rel = $index | Where-Object { $_.version -like 'v24.*' -and $_.files -contains 'win-x64-zip' } | Select-Object -First 1
        if (-not $rel) { throw 'Node 24 release not found' }
        $v = $rel.version
        $zip = Join-Path $DL "node-$v.zip"
        Fetch "https://nodejs.org/dist/$v/node-$v-win-x64.zip" $zip
        $tmp = Join-Path $DL 'node-x'
        Unzip $zip $tmp
        $inner = Get-ChildItem $tmp -Directory | Select-Object -First 1
        Move-Item $inner.FullName $nodeDir
        Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }

    # PATH for this process (same as start.ps1)
    $env:PATH = "$(Join-Path $venv 'Scripts');$ffbin;$nodeDir;$env:PATH"
    $env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $RT 'ms-playwright'
    $env:PYTHONUTF8 = '1'; $env:PYTHONIOENCODING = 'utf-8'

    # ---------- 6. Playwright (PDF renderer) + Chromium ----------
    Push-Location $Root
    $c = Run (Join-Path $nodeDir 'npm.cmd') @('install', '--no-save', '--no-package-lock', '--no-audit', '--no-fund', 'playwright@1.56.1')
    Pop-Location
    if ($c -ne 0) { throw 'playwright npm install failed' }
    $c = Run $node @((Join-Path $Root 'node_modules\playwright\cli.js'), 'install', 'chromium')
    if ($c -ne 0) {
        $edge = Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'
        if (-not (Test-Path $edge)) { $edge = Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe' }
        if (Test-Path $edge) {
            Log "Chromium download failed. Falling back to installed Edge: $edge"
            $json = '{"browser": ' + (ConvertTo-Json $edge) + '}'
            [IO.File]::WriteAllText((Join-Path $Root 'runtime.local.json'), $json, (New-Object Text.UTF8Encoding($false)))
        } else { throw 'no browser available for PDF rendering' }
    }

    # ---------- 7. Checks ----------
    Log '==== versions ===='
    $results['python']  = (Run $py @('--version')) -eq 0
    $results['ffmpeg']  = (Run 'ffmpeg' @('-hide_banner', '-version')) -eq 0
    $results['ffprobe'] = (Run 'ffprobe' @('-hide_banner', '-version')) -eq 0
    $results['node']    = (Run $node @('--version')) -eq 0
    $results['yt-dlp']  = (Run $py @('-m', 'yt_dlp', '--version')) -eq 0
    $results['crv']     = (Run 'crv' @('--help')) -eq 0
    $results['whisper/torch import'] = (Run $py @('-c', 'import whisper, torch, PIL, pypdf, pypdfium2; print(torch.__version__)')) -eq 0

    Log '==== smoke: PDF render ===='
    $smoke = Join-Path $RT 'smoke'
    New-Item -ItemType Directory -Force -Path $smoke | Out-Null
    $html = Join-Path $smoke 'test.html'
    $page = '<!doctype html><html lang="ja"><meta charset="utf-8"><style>@page{size:A4;margin:0}.page{width:210mm;height:297mm;padding:20mm;box-sizing:border-box;font-family:"Yu Gothic",Meiryo,sans-serif}</style><body><div class="page"><div class="page-content"><h1>' + [char]0x30C6 + [char]0x30B9 + [char]0x30C8 + ' PDF</h1><p>crv-pdf-prototype local render check.</p></div></div></body></html>'
    [IO.File]::WriteAllText($html, $page, (New-Object Text.UTF8Encoding($false)))
    Run $node @((Join-Path $Root 'render.cjs'), $html, $smoke) | Out-Null
    $results['PDF render'] = Test-Path (Join-Path $smoke 'document.pdf')

    Log '==== smoke: crv extraction on a 4s generated video (first run downloads the Whisper base model) ===='
    $vid = Join-Path $smoke 'test.mp4'
    Run 'ffmpeg' @('-y', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc=duration=4:size=640x360:rate=10', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=4', '-shortest', '-pix_fmt', 'yuv420p', $vid) | Out-Null
    $crvOut = Join-Path $smoke 'crv-out'
    $env:XDG_CACHE_HOME = Join-Path $RT 'cache'
    Run $py @((Join-Path $Root 'crv_worker.py'), $vid, '-o', $crvOut, '--max-frames', '4') | Out-Null
    Remove-Item Env:XDG_CACHE_HOME
    $results['crv extraction'] = Test-Path (Join-Path $crvOut 'frames.json')
    if (-not $results['crv extraction']) { $results['crv extraction'] = [bool](Get-ChildItem $crvOut -Recurse -Filter *.jpg -ErrorAction SilentlyContinue) }

    Log '==== offline unit tests ===='
    Push-Location $Root
    $results['unit tests (infrastructure)'] = (Run $py @('-m', 'unittest', 'test_infrastructure', 'test_model_catalog')) -eq 0
    Pop-Location
}
catch {
    Log "SETUP ERROR: $($_.Exception.Message)"
    $results['setup'] = $false
}

Log '==== RESULT ===='
foreach ($k in $results.Keys) { Log ("{0,-28} {1}" -f $k, $(if ($results[$k]) { 'OK' } else { 'NG' })) }
Log "==== setup finished $(Get-Date -Format s) ===="
Write-Host ''
Write-Host "Log: $Log"
