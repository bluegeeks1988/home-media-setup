# Operations, backups and troubleshooting

## Update selectively
`docker compose pull jellyfin seerr radarr sonarr lidarr prowlarr bazarr qbittorrent gluetun caddy`
`docker compose up -d` (do this in a maintenance window, after backing up). Role Manager requires `docker compose --profile roles up -d --build seerr-roles`. Never use `docker compose down -v` unless you intend to **destroy persistent volumes**.

## Backup
Back up `${MEDIA_ROOT}/appdata`, the Compose directory and `.env` **securely**, plus Docker named volumes `seerr_config`, `caddy_data`, `caddy_config` and optional `seerr_roles_data`. Named volumes are **not** part of `${MEDIA_ROOT}/appdata`. Use offline/cold backups when possible; verify restores. Do not publish backup archives or VPN keys to GitHub.

## Diagnostics
- `docker compose config -q` — YAML validation
- `docker compose ps` — container status
- `docker compose logs --tail=100 SERVICE` — container logs
- Caddy port 80/443 bind error: inspect Windows listeners and router; stop conflicting server before retry.
- Caddyfile mount 'not a directory': ensure `caddy/Caddyfile` is a **file**, not folder.
- qBittorrent WebUI is mapped to `localhost:8081` (not `8080`); Windows Firefox blocks SIP port 5060, so Role Manager uses 5070.
- Prowlarr: Docker service hostnames work **inside Docker**, `localhost` is appropriate for Windows host browser.
- Download completes but missing Jellyfin: check ARR Activity → Queue and History; import into `/data/media` must happen before Jellyfin scan/Connect events. Enable scheduled Jellyfin scans as fallback for Windows bind-mounted directories.
- Seerr users cannot access a library: Jellyfin remote access and library permissions are independent of Seerr request permissions.
- Proton VPN only protects qBittorrent sharing Gluetun's namespace. Other containers are not automatically tunneled.
- FlareSolverr is optional and may not solve modern Cloudflare challenges.
