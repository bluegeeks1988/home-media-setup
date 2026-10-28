# Experimental Seerr Role Manager v0.3

See [repository role-manager instructions](../docs/ROLE-MANAGER.md). This source is independent of Seerr and is experimental. Automatic new-user assignment has a known issue with baseline and failed API updates. Test in a non-production environment before using it for real accounts.

# Seerr Role Manager — MVP v0.1

Standalone local-only admin application for reusable Seerr roles. No changes to Seerr's files or database.

## Deploy to your Windows Docker Desktop stack

1. Extract this ZIP so the Dockerfile is at `D:\Docker\seerr-roles\Dockerfile` and the source is at `D:\Docker\seerr-roles\app\main.py`.
2. In Seerr, open **Settings → General**, copy the API key (never share it).
3. In `D:\Docker\arr-stack\.env`, add:
   ```env
   SEERR_API_KEY=replace-with-your-seerr-api-key
   ROLE_MANAGER_PASSWORD=choose-a-long-unique-password
   ROLE_MANAGER_SESSION_SECRET=replace-with-64-random-hex-characters
   ```
   Generate a secret with PowerShell:
   ```powershell
   -join ((1..64) | ForEach-Object { '0123456789abcdef'[(Get-Random -Minimum 0 -Maximum 16)] })
   ```
4. Paste the `seerr-roles:` service from `docker-compose.override.example.yml` under `services:` in your existing `D:\Docker\arr-stack\docker-compose.yml`. Add `seerr_roles_data:` under the existing top-level `volumes:` (do not add a second `volumes:` heading). The Compose project already has `arr_network` as its default network.
5. Start:
   ```powershell
   cd D:\Docker\arr-stack
   docker compose config -q
   docker compose up -d --build --no-deps seerr-roles
   docker compose logs --tail=40 seerr-roles
   ```
6. Visit `http://127.0.0.1:5060`, sign in with `ROLE_MANAGER_PASSWORD`.

**Do not add the Role Manager to Caddy or publicly expose port 5060.** Your Jellyfin/Seerr can remain available via their domains.

## Use

1. Configure a **non-admin** Seerr account with the permissions you want to use as a template (e.g. Friends: Request movies/series, but no Auto-Approve).
2. In Role Manager, **Create role** > choose that account to copy its permission bitmask; enter movie/TV quota + time window.
3. Repeat for Family, VIP, etc.
4. On the dashboard, assign a role to a user; this immediately updates permission settings and user-specific quota settings using the Seerr API.
5. When editing a role, click **Sync assigned users** to propagate the changes.

### Behaviour and limitations

- v0.1 provides **manual sync** on assignment and on demand for all assigned users; it does NOT automatically reconcile out-of-band permission changes or assign a default role to newly added accounts.
- To use Seerr's global request limits instead of a user-specific override, leave quota limit and days empty.
- Removing an assignment leaves the user's current Seerr permissions unchanged.
- Admin accounts (ID 1 or ADMIN bit) are intentionally blocked from assignment or modifications.
- A role's permission template is copied from an existing **non-admin** Seerr user, so no permission numbers are guessed.
- If a permissions update succeeds but quota update fails, the user may be partially updated. The audit log records successful full syncs; inspect Seerr manually for partial failures.
- This app assumes the Seerr admin API key has authority for `/api/v1/user` and `/user/:id/settings/*`. Confirm API behaviour on your installed Seerr version before bulk synchronisation.
- For security, the Web UI is bound to Windows loopback (`127.0.0.1:5060`). No public registration, no API key in browser JavaScript, CSRF on write actions, session cookies HttpOnly/SameSite Strict.
- This is an initial project build, not tested against your live installation. Make a Seerr configuration backup and test with a non-admin account before managing family/friends.
- The optional Docker volume `seerr_roles_data` stores the SQLite database. Back it up with your other Docker volumes.

## v0.2 - native permission template editor

The Roles editor now exposes all user-facing permission toggles from Seerr's
`server/lib/permissions.ts`, verified on 28 October 2026. It includes request,
auto-approval, auto-request, 4K, issue, blocklist and viewing permissions.
The Admin permission is displayed but locked: administrator accounts and
privilege assignment must be managed directly inside Seerr.

Existing roles, assignments and audit history are preserved in the same SQLite
volume. Rebuild with `docker compose up -d --build --no-deps seerr-roles`.
Role edits are not pushed until clicking **Sync assigned users**.

**Security:** A template can grant `Manage Users` or `Manage Requests`; limit
use of the Role Manager to trusted administrators. New roles default to no
permissions. No change to the Seerr container is required.

## v0.3 automatic default role assignment

Open **Automation** in the Role Manager. Select a previously created role and enable automatic assignment. On first activation, the app records all currently existing Seerr user IDs without altering them. Every five minutes, it searches for newly appearing accounts and applies the selected role and quotas to non-admin accounts. API failures are logged; failed users will not be automatically retried to prevent unintended overwrites (assign manually). Admin accounts and users with existing assignments are skipped. Disable automation to suspend future automatic assignments.

The user snapshot and automation settings are stored in the existing SQLite volume. No Compose change is needed if v0.2 already runs. Back up the Seerr Role Manager and Seerr configuration volumes before upgrading. This feature has not been integration-tested against your live server.
