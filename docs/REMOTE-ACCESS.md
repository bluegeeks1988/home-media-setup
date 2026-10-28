# Domain, DNS, HTTPS and remote users

## Prerequisites
- A domain you control, public reachable WAN IPv4 (or an alternative such as a VPS/private VPN). Check WAN IP against external IP to spot CGNAT/double NAT.
- Stable LAN IP / DHCP reservation for the Windows Docker host.
- Windows Firewall rules scoped to inbound TCP **80 and 443** for Caddy; router forward TCP 80→80 and 443→443 to the host LAN IP.
- DNS manager (e.g. names.co.uk or Cloudflare in **DNS-only** mode): A records `media` and `requests` pointing to **your own current public IP**. Remove stale AAAA records if IPv6 isn't set up. Never copy example public IP values.

## Caddy
Edit `.env` with `DOMAIN=yourdomain.example` and use `caddy/Caddyfile`. The bundled config exposes only `media.DOMAIN`→Jellyfin and `requests.DOMAIN`→Seerr. Start with `docker compose up -d caddy`; verify `docker compose logs caddy` for certificate issuance. Keep Caddy's `/data` named volume for certificate persistence.

## Jellyfin
Create separate non-admin accounts; grant remote access and explicit library permissions. Under Jellyfin Dashboard → Networking, add the Docker-network IP of Caddy to **Known Proxies** to correctly process forwarded client IPs; Docker container IPs may change. See Jellyfin's reverse proxy documentation. Do not give friends Docker, ARR or Seerr administration access.

## Seerr
Import Jellyfin users and give each appropriate request permissions/quotas. Set restricted defaults for new accounts. Requests are separate from media playback privileges.

## Verify
Test `https://media.yourdomain.example` and `https://requests.yourdomain.example` from **mobile data**, not the home Wi-Fi. Test login and a legitimate playback. If timeout, check DNS, public IP, CGNAT, port forwarding and Windows Firewall. If 502, check container connectivity and Caddy logs. If TLS fails, check certificate issuance and port 80/443 reachability.

## Hardening
Only public Caddy, not Prowlarr/Radarr/Sonarr/Lidarr/Bazarr/qBittorrent/Role Manager; all of those are bound to 127.0.0.1 in the sample. Strong unique passwords and updates are mandatory. Restrict Jellyfin and Seerr access to authorised users. Disable unused UPnP rules on your router. Configure dynamic DNS when public IP changes; Caddy does not update DNS for you. Check upload bandwidth, transcoding and host sleep settings.
