# Download one video (YouTube / X) into .\downloads using the local yt-dlp. No API is used.
# Default: up to 720p (enough for the app's 1280px frames). If the file is over the
# Render upload limit (90MB), an extra copy "...-90MB.mp4" is made with FFmpeg.
param([string]$Url)
$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
$Root = $PSScriptRoot
$RT   = Join-Path $Root '_runtime'
$py   = Join-Path $RT 'venv\Scripts\python.exe'
$ffbin = Join-Path $RT 'ffmpeg\bin'
if (-not (Test-Path $py)) { Write-Host 'Setup has not finished. Run 1_setup.bat first.'; exit 1 }
$env:PATH = "$(Join-Path $RT 'venv\Scripts');$ffbin;$(Join-Path $RT 'node');$env:PATH"
$env:PYTHONUTF8 = '1'
if (-not $Url) { $Url = Read-Host 'Video URL' }
$Url = $Url.Trim()
if ($Url -notmatch '^https://') { Write-Host 'Please paste a URL that starts with https://'; exit 1 }
$out = Join-Path $Root 'downloads'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$node = Join-Path $RT 'node\node.exe'
$pathFile = Join-Path $out '.last-download.txt'
Remove-Item $pathFile -ErrorAction SilentlyContinue

& $py -m yt_dlp --ignore-config --no-playlist `
    --js-runtimes "node:$node" `
    -S 'res:720,ext:mp4:m4a' --merge-output-format mp4 `
    --ffmpeg-location $ffbin `
    -o (Join-Path $out '%(title).80s [%(id)s].%(ext)s') `
    --print-to-file 'after_move:filepath' $pathFile `
    $Url
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $pathFile)) {
    Write-Host ''
    Write-Host "Download failed (exit $LASTEXITCODE). Send the messages above to Claude."
    exit 1
}
$file = (Get-Content $pathFile -Encoding UTF8 | Where-Object { $_ } | Select-Object -Last 1).Trim()
Remove-Item $pathFile -ErrorAction SilentlyContinue
$limit = 90MB
$size = (Get-Item -LiteralPath $file).Length
Write-Host ''
Write-Host ("Downloaded: {0} ({1:N1} MB)" -f (Split-Path $file -Leaf), ($size / 1MB))

if ($size -gt $limit) {
    Write-Host 'Over 90MB: making a smaller copy for the Render version...'
    $dur = [double](& (Join-Path $ffbin 'ffprobe.exe') -v error -show_entries format=duration -of csv=p=0 $file)
    if ($dur -le 0) { Write-Host 'Could not read the video length.'; exit 1 }
    $small = [IO.Path]::Combine((Split-Path $file), [IO.Path]::GetFileNameWithoutExtension($file) + '-90MB.mp4')
    # Aim for ~80MB total so the result stays under 90MB.
    $audioK = 96
    $videoK = [math]::Floor((80 * 8 * 1024 / $dur) - $audioK)
    if ($videoK -lt 150) { Write-Host 'This video is too long to fit in 90MB with usable quality. Use the local version (1GB limit).'; exit 1 }
    & (Join-Path $ffbin 'ffmpeg.exe') -y -hide_banner -loglevel error -i $file `
        -c:v libx264 -preset veryfast -b:v "${videoK}k" -maxrate "$([math]::Floor($videoK*1.5))k" -bufsize "$($videoK*2)k" `
        -vf "scale='min(1280,iw)':-2" -c:a aac -b:a "${audioK}k" -movflags +faststart $small
    if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $small)) {
        Write-Host ("Smaller copy: {0} ({1:N1} MB) - upload this one to Render." -f (Split-Path $small -Leaf), ((Get-Item -LiteralPath $small).Length / 1MB))
    } else { Write-Host 'Could not make the smaller copy.' }
}
Write-Host ''
Write-Host "Saved to: $out"
Start-Process explorer.exe $out
