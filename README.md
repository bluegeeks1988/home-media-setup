# Home Media Stack — Docker Desktop + Jellyfin + Seerr

> **Self-hosted media automation, private family streaming and request management.** Windows Docker Desktop example with configurable paths and domain; core components can also be adapted for Linux.
>
> **Status:** Community starter kit. Core Compose is an example intended for fresh deployments, not a tested one-click production appliance. Optional Role Manager **v0.3 is experimental**, with a documented automatic-assignment bug.

## Overview

```text
Family & friends --> HTTPS media.example.com --> Caddy --> Jellyfin
Family & friends --> HTTPS requests.example.com --> Caddy --> Seerr
                                                           |      |
                                                         Radarr Sonarr
                                                           \      /
                                                         Prowlarr
                                                           |
                                                    qBittorrent --> Gluetun --> Proton VPN
                                                           |
                                                         /data
                                                           |
                                                        Jellyfin
Admin only --> localhost ARR tools, Ombi, FlareSolverr, Role Manager
```

The media stack operates on your own hardware. Jellyfin streams your media, Seerr handles movie/TV requests, Radarr/Sonarr/Lidarr organise libraries, qBittorrent handles transfers, Gluetun restricts qBittorrent's network path through Proton VPN, Prowlarr manages indexers, Bazarr handles subtitles, and Caddy serves HTTPS. Ombi and FlareSolverr are optional extras. Experimental **Seerr Role Manager** provides reusable user permissions and quotas.

## Quick start (Windows)

**Prerequisites:** Windows 10/11, Docker Desktop in Linux containers mode, a local drive for persistent media, paid Proton VPN with P2P/WireGuard for this example. A public domain, router access and suitable WAN connectivity are required **only** for remote HTTPS access.

```powershell
# Clone the repository or extract the GitHub ZIP to D:\Docker\home-media-stack
cd D:\Docker\home-media-stack
Copy-Item .env.example .env
.\scripts\initialize.ps1 -Root 'D:\Docker'
notepad .env
# Set MEDIA_ROOT, DOMAIN and your own Proton WireGuard private key

docker compose config -q
docker compose up -d gluetun qbittorrent radarr sonarr lidarr prowlarr bazarr jellyfin seerr
```

Detailed setup: **[Windows installation](docs/INSTALL-WINDOWS.md)**. Keep transfers disabled until the VPN route and forwarding hook have been verified. The provided Gluetun hook and qBittorrent config may require adjustment across upstream versions.

**Public remote access:** Follow **[Domain, DNS, router and Caddy instructions](docs/REMOTE-ACCESS.md)** *after* configuring media accounts and permissions. Then run `docker compose up -d caddy`.

**Role Manager:** [Optional experimental module](docs/ROLE-MANAGER.md) — `docker compose --profile roles up -d --build seerr-roles`.

**Extras:** `docker compose --profile extras up -d ombi flaresolverr`.

## Services

| Service | Local URL | Notes |
|---|---|---|
| Jellyfin | http://localhost:8096 | Media playback |
| Seerr | http://localhost:5055 | Movie/TV requests |
| Radarr | http://localhost:7878 | Movies |
| Sonarr | http://localhost:8989 | TV |
| Lidarr | http://localhost:8686 | Music |
| Prowlarr | http://localhost:9696 | Indexers |
| Bazarr | http://localhost:6767 | Subtitles |
| qBittorrent | http://localhost:8081 | VPN-routed downloads |
| Ombi (optional) | http://localhost:3579 | Music and other requests |
| FlareSolverr (optional) | http://localhost:8191 | Browser challenge helper (limited reliability) |
| Role Manager (experimental) | http://localhost:5070 | Private admin; do not expose publicly |
| Caddy | HTTPS on 443 | Public reverse proxy |

In-container hostnames are service names (`http://jellyfin:8096`, `http://seerr:5055`, `http://gluetun:8081`). `localhost` in a web browser refers to the Windows host. Only Caddy is published publicly in the Compose example; others bind to Windows loopback.

## Directory layout

```text
MEDIA_ROOT/
  appdata/       # persistent app configurations
  data/
    torrents/{movies,tv,music,incomplete}/
    media/{movies,tv,music}/
```

Each ARR container sees its shared media root at `/data`. The sample uses `MEDIA_ROOT=D:/Docker`, but **do not put your own paths in a public repository**. Use the `.env` example.

## Features / current limitations

- Jellyfin's automatic media discovery can use ARR Connect notifications, real-time monitoring and periodic scans. Docker Desktop Windows bind mounts may not consistently relay filesystem events.
- Seerr covers movies and TV; Lidarr manages music releases, with Ombi optional for music requests. Individual track requests can be limited by release availability.
- qBittorrent must remain behind Gluetun. Gluetun health alone is not proof of all traffic isolation; test VPN egress and fail-closed behaviour.
- Proton forwarding ports can change. Validate qBittorrent's listening port matches the assigned value.
- Role Manager v0.3 auto-assignment may fail and skip retry; **do not rely on it for unattended user permissions**.
- A home IP may change; set up dynamic DNS. CGNAT requires an alternative remote-access approach.

## Documentation

- [Installation](docs/INSTALL-WINDOWS.md)
- [Remote access, DNS, Caddy and family users](docs/REMOTE-ACCESS.md)
- [Role Manager](docs/ROLE-MANAGER.md)
- [Updates, backup and troubleshooting](docs/OPERATIONS.md)
- [Security guidance](SECURITY.md)
- [Contributing](CONTRIBUTING.md)

## Licence and upstream projects

The example configuration, original documentation and original Role Manager glue code in this repository are offered under the included **MIT licence**. Upstream images and projects (Jellyfin, Seerr, qBittorrent, Gluetun, etc.) have their **own independent licences and trademarks**; this repository does not relicense or bundle those upstream products. Review upstream licences before redistributing builds.

## Authorisation

Use this stack only with media you own or are entitled to access, and grant friends access only where your rights permit it. This guide does not provide indexers or content sources.
