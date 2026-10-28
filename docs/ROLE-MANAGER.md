# Optional Seerr Role Manager (experimental v0.3)

This repository includes a separately developed Role Manager under `role-manager/`, supporting reusable permission/quotas profiles and a local-only management UI. **This is not an official Seerr component.** It uses Seerr's administration API and needs testing before production use.

1. Read `role-manager/README.md` for the original app's functionality and limitations.
2. Get Seerr API key from its settings; set `SEERR_API_KEY`, `ROLE_MANAGER_PASSWORD`, and `ROLE_MANAGER_SESSION_SECRET` in `.env`.
3. `docker compose --profile roles up -d --build seerr-roles`
4. Visit `http://127.0.0.1:5070`. Never publicly expose this service or its key.
5. Create roles and test assignments against a **non-admin disposable user**, verify permissions and quotas in Seerr.
6. **Known issue in v0.3:** newly discovered users can be marked seen before a failed assignment succeeds and not retried; users present at baseline are excluded. Audit failures, perform manual assignments when needed and do not rely on automatic assignment until fixed and tested.
7. Persist and back up Docker volume `home-media_seerr_roles_data` (actual volume name depends on Compose project name).

The application is provided as experimental source. Upstream Seerr updates may change API behaviour. Review source and API compatibility before deployment.
