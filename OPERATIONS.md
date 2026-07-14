# WorkHub Operations Guide

## Live architecture

```text
Browser clients
        |
        | HTTPS + JWT
        v
Vercel: React static build + FastAPI serverless function (api/index.py)
        |
        | TLS Postgres connection
        v
Vercel Postgres (Neon) database: workhub
```

- Live API base: `https://YOUR-PROJECT.vercel.app/api`
- Health check: `https://YOUR-PROJECT.vercel.app/api/health`
- API documentation: `https://YOUR-PROJECT.vercel.app/api/docs`
- Source repository: `https://github.com/prashanth-ds-ml/workhub-office-time-tracker`
- Legacy desktop release: `release\WorkHub-Installer.zip`
- Server release: `release\WorkHub-Server.zip`

Postgres credentials and server secrets must remain in Vercel project
environment variables. Never distribute them with any client package.

## Vercel environment

The Vercel project requires:

| Variable | Purpose |
|---|---|
| `WORKHUB_ENV=production` | Enables production safeguards |
| `POSTGRES_URL` | Postgres connection string (auto-injected by the Vercel Postgres integration, or a Neon URL) |
| `WORKHUB_JWT_SECRET` | Signs authentication tokens |
| `WORKHUB_JWT_EXPIRE_HOURS=12` | Login-token lifetime |
| `WORKHUB_BOOTSTRAP_SECRET` | Private key required for Admin registration |
| `WORKHUB_ALLOW_SELF_REGISTRATION=true` | Allows User self-registration |
| `WORKHUB_CORS_ORIGINS` | Optional comma-separated browser origins for custom web hosts |

Do not expose `POSTGRES_URL`, `WORKHUB_JWT_SECRET`, or
`WORKHUB_BOOTSTRAP_SECRET`.

If WorkHub is served from a browser origin other than the default local Vite
origins or the same hosted domain as FastAPI, set `WORKHUB_CORS_ORIGINS`
explicitly. Credentialed requests no longer allow the `"null"` origin.

## Serverless behavior

Vercel serverless functions spin up on demand and may go cold after a period
of inactivity. WorkHub handles this by:

- showing the login window immediately;
- waking the server in a background thread;
- allowing manual `Wake / reconnect`;
- waiting up to 90 seconds for login or registration;
- sending a health heartbeat every 10 minutes during office hours.

The first request after idle time can therefore be slow while the function
cold-starts. Postgres data remains persistent regardless of function state.
The React app itself is served as a static site from Vercel's CDN and has no
cold start.

## Postgres initialization

Local `.env` supports:

```text
POSTGRES_URL=...
```

(also checked: `POSTGRES_URL_NON_POOLING`, `DATABASE_URL`)

Initialize a clean database:

```powershell
.\.venv\Scripts\python.exe initialize_postgres.py
```

This creates all tables and indexes plus:

- seven attendance-policy rows;
- one universal company work-policy row.

It does not create users, sessions, calendar events, or announcements.

## Account registration

The Create Account page has two explicit choices.

### Employee / User

- Does not require the bootstrap key.
- Requires `WORKHUB_ALLOW_SELF_REGISTRATION=true`.
- Receives employee-only navigation and permissions.

### Administrator

- Requires the exact `WORKHUB_BOOTSTRAP_SECRET`.
- Receives the complete Admin Console.
- The bootstrap key must only be given to authorized administrators.

Both roles use the same Sign In page after registration.

## Installing on a Windows laptop

1. Install Python 3.10 or newer and enable `Add Python to PATH`.
2. Extract `WorkHub-Installer.zip`.
3. Double-click `Install WorkHub.bat`.
4. Enter:

```text
https://YOUR-PROJECT.vercel.app/api
```

5. Wait for dependencies to install.
6. Open the WorkHub shortcut from the Desktop or Start menu.
7. Register as Employee/User or Administrator.

The application is installed under:

```text
%LOCALAPPDATA%\WorkHubApp
```

Client configuration is stored under:

```text
%LOCALAPPDATA%\WorkHub\client_config.json
```

## Building a new desktop release

Run:

```powershell
.\build_share_package.ps1
```

Output:

```text
release\WorkHub-Installer.zip
```

The build runs the integration test before producing the package.

## Deploying application updates

Backend changes:

```powershell
git add -A
git commit -m "Describe the update"
git push
```

Vercel automatically deploys the latest `main` commit (or opens a preview
deployment for other branches/PRs).

Legacy desktop changes require:

```powershell
.\build_share_package.ps1
```

Then redistribute the new installer ZIP or replace the installed source files.

## Verification commands

Local syntax and integration:

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py storage.py desktop_app.py admin_panel.py
.\.venv\Scripts\python.exe integration_smoke.py
.\.venv\Scripts\python.exe postgres_integration_smoke.py
```

Live health:

```powershell
Invoke-RestMethod https://YOUR-PROJECT.vercel.app/api/health
```

Expected storage values:

```text
environment: production
backend: postgres
connected: true
database: workhub
```

## Common troubleshooting

### Vercel returns `404 NOT_FOUND` for `/api/...`

Confirm `vercel.json`'s rewrite for `/api/(.*)` points at `/api/index.py` and
that the Python function built successfully in the deployment logs.

### Vercel build fails installing Python dependencies

Confirm `requirements.txt` versions are compatible with the Vercel Python
runtime; check the build logs for the exact package that failed.

### Vercel fails with missing bootstrap secret

Add `WORKHUB_BOOTSTRAP_SECRET` under Vercel Project Settings → Environment
Variables and redeploy.

### Login returns `401`

The email/password combination is invalid, the account is inactive, or the
user has not registered yet.

### Registration says invalid Admin key

The value must exactly match Vercel's `WORKHUB_BOOTSTRAP_SECRET`.

### Desktop double-click opens nothing

Confirm `client_config.json` contains the Vercel URL (including the `/api`
path). The application reads UTF-8 files with or without a BOM. Reinstall
using the latest ZIP if required.

### Server is starting

Wait up to 90 seconds or click `Wake / reconnect`. This is expected while a
serverless function cold-starts after being idle.

### Desktop shortcut location

On systems using OneDrive folder redirection, the shortcut may be under:

```text
%USERPROFILE%\OneDrive\Desktop
```

The Start menu shortcut is also installed.

## Security rules

- Never distribute Postgres credentials.
- Never distribute the JWT secret.
- Give the bootstrap key only to real administrators.
- Employee browsers communicate only with the Vercel HTTPS deployment.
- Passwords are stored as PBKDF2 hashes.
- Production mode rejects JSON fallback.
- Admin and User permissions are enforced by the backend, not only by the UI.

## Backup and reset

Use the Postgres provider's (Vercel Postgres/Neon) backup/branching/export
facilities before destructive changes.

`reset_workhub_data.py --confirm` removes operational data and resets the
Admin-claim marker. It must only be run intentionally by an administrator.

## Beta rollout

For a small employee beta, keep the rollout limited to a few browser users,
confirm the login, attendance, announcements, and admin edit paths, and watch
for mobile/table responsiveness issues during the first few days.
