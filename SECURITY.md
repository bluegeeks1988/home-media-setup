# Security policy

**Never commit** `.env`, WireGuard `.conf` files, API keys, database volumes, media, identity/account details or generated certificates. The examples intentionally use placeholders. Public exposure should be limited to Caddy (TCP 80/443), not the ARR services, qBittorrent, Docker daemon or Role Manager. Use distinct non-admin Jellyfin accounts and strong credentials. Test remote connectivity and logs before inviting anyone.

Do not use this platform to distribute media without the necessary rights. Download only media you are authorised to obtain; respect providers' terms and applicable law.

For vulnerabilities in the included experimental Role Manager, open a private security report with the repository maintainer rather than publishing tokens or attack details.
