# Create or remove a Startup shortcut so chat mode starts at Windows sign-in (no admin needed).
param([switch]$Remove)
$startup = [Environment]::GetFolderPath('Startup')
$link = Join-Path $startup 'CRV PDF chat mode.lnk'
if ($Remove) { Remove-Item $link -ErrorAction SilentlyContinue; Write-Host 'Autostart removed.'; exit 0 }
$shell = New-Object -ComObject WScript.Shell
$s = $shell.CreateShortcut($link)
$s.TargetPath = Join-Path $PSScriptRoot '4_chat_mode.bat'
$s.WorkingDirectory = $PSScriptRoot
$s.WindowStyle = 7
$s.Save()
Write-Host "Autostart added: $link"
Write-Host 'Chat mode will start (minimized) the next time you sign in to Windows.'
