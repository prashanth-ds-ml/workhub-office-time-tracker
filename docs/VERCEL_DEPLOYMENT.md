# Deploy WorkHub Web and API on Vercel

## Current services

- Vercel project: React static build (`web_app/`) + FastAPI serverless function (`api/index.py`)
- Postgres: Vercel Postgres (Neon-backed)

## Layout

- `vercel.json` builds `web_app/` as a static site (Vite `dist` output) and
  `api/index.py` as a Python serverless function.
- `api/index.py` mounts the existing FastAPI app (`app.py`) under `/api`, so all
  routes defined in `app.py` (e.g. `/login`) are reachable at `/api/login`.
- `web_app/.env.production` sets `VITE_API_URL=/api` so the built frontend
  calls the mounted API path in production; local dev still hits the
  same-origin root paths served by `uvicorn app:app`.
- Rewrites in `vercel.json` send `/api/*` to the function and everything else
  to the built SPA's `index.html` for client-side routing.

## Vercel environment variables

| Key | Value |
|---|---|
| `WORKHUB_ENV` | `production` |
| `POSTGRES_URL` | Auto-injected when the Vercel Postgres integration is attached, or a Neon connection string |
| `WORKHUB_JWT_SECRET` | Long random secret |
| `WORKHUB_JWT_EXPIRE_HOURS` | `12` |
| `WORKHUB_BOOTSTRAP_SECRET` | Private key required for Admin registration |
| `WORKHUB_ALLOW_SELF_REGISTRATION` | `true` or `false` |
| `WORKHUB_EMAIL_DOMAIN` | `sims.healthcare` |
| `WORKHUB_PASSWORD_RESET_MINUTES` | `30` |
| `WORKHUB_SMTP_HOST` / `WORKHUB_SMTP_PORT` / `WORKHUB_SMTP_TLS` / `WORKHUB_SMTP_USER` / `WORKHUB_SMTP_PASSWORD` / `WORKHUB_SMTP_FROM` | SMTP credentials for password reset emails |

## First deploy

1. Attach a Vercel Postgres (Neon) database to the project so `POSTGRES_URL` is set automatically, or set it manually to a Neon connection string.
2. Run `python initialize_postgres.py` once (locally, pointed at the same `POSTGRES_URL`) to create tables/indexes and seed default attendance policies.
3. Deploy. Vercel runs `npm ci && npm run build` in `web_app/` and provisions `api/index.py` as a Python function.
4. Verify:

```text
https://YOUR-PROJECT.vercel.app/api/health
```

The response must report:

- `status: ok`
- `environment: production`
- `storage.backend: postgres`
- `storage.connected: true`

The same deployment serves:

- `/` and browser routes: React application (static, served from the CDN — no cold start)
- `/api/docs`: API documentation
- `/api/health`: service and Postgres health
- `/api/*`: existing API endpoints used by desktop clients (update the desktop client's configured API base URL to include the `/api` prefix)

## Notes

- Each serverless invocation may run on a fresh instance; `app.py`'s in-memory
  read cache (`WORKHUB_CACHE_TTL_SECONDS`, default 2s) is per-instance, so
  concurrent cold instances can briefly serve slightly stale reads across each
  other for up to that TTL. All writes are persisted to Postgres immediately,
  so this only affects read staleness, not data loss.
- The browser uses same-origin HTTP-only session cookies. Bearer-token support
  remains unchanged for the Python desktop application (update its API base
  URL to point at `/api`).
