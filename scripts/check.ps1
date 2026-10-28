$ErrorActionPreference='Stop'
docker compose config -q
if ($LASTEXITCODE -ne 0) { throw 'Compose validation failed' }
docker compose ps
Write-Host "Check VPN logs, HTTPS issuance and application health manually:"
Write-Host 'docker compose logs --tail=50 gluetun caddy seerr'
