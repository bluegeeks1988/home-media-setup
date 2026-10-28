param([string]$Root = 'D:\Docker')
$dirs = @('appdata\gluetun','appdata\radarr','appdata\sonarr','appdata\lidarr','appdata\prowlarr','appdata\bazarr','appdata\qbittorrent','appdata\jellyfin','appdata\ombi','data\torrents\incomplete','data\torrents\movies','data\torrents\tv','data\torrents\music','data\media\movies','data\media\tv','data\media\music')
foreach ($dir in $dirs) { New-Item -ItemType Directory -Force -Path (Join-Path $Root $dir) | Out-Null }
Write-Host "Created media folders under $Root. Set MEDIA_ROOT in .env to $($Root -replace '\\','/')."
