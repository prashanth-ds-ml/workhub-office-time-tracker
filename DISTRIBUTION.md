# WorkHub for Windows

## Install and run

1. Install Python 3.10 or newer and enable `Add Python to PATH`.
2. Extract `WorkHub-Installer.zip`.
3. Double-click `Install WorkHub.bat`.
4. The installer creates an isolated environment and Desktop shortcut.
5. The first registered account becomes the Admin.
6. Later registrations become Employee accounts.

WorkHub stores local fallback data under:

`%LOCALAPPDATA%\WorkHub\data`

## Shared company data

All colleagues connect to one central WorkHub API. Employee laptops never
connect directly to MongoDB.

Production deployment:

1. Create a MongoDB database/user restricted to the WorkHub database.
2. Configure the server using `.env.production.example`.
3. Set `WORKHUB_ENV=production`, `MONGO_URI`, `MONGO_DB`, and a long random
   `WORKHUB_JWT_SECRET`.
4. Set `WORKHUB_BOOTSTRAP_SECRET`. The first Admin enters this value in the
   registration page's company setup-code field.
5. Set `WORKHUB_ALLOW_SELF_REGISTRATION=true` only if employees may create
   their own accounts. Otherwise, Admins create accounts from Employees.
6. Run the API behind HTTPS using `run_production_server.ps1` or your normal
   service/container platform.
7. During desktop installation, enter the HTTPS API URL.

For a container deployment, copy `.env.docker.example` to `.env`, replace
every secret, then run:

```powershell
docker compose up -d --build
```

Place the API behind your company's HTTPS reverse proxy before distributing
the client URL.

## Render deployment

Render is the recommended managed host for this project. The repository
includes `render.yaml`; see `RENDER_DEPLOYMENT.md`.

Use a Starter web service or higher for office use. The Free service sleeps
when idle and introduces cold-start delays.

When a shared API URL is configured, the desktop refuses to start a private
local backend if the company server is unavailable.

## Migrating existing JSON data

```powershell
python migrate_json_to_mongodb.py `
  --source "$env:LOCALAPPDATA\WorkHub\data" `
  --mongo-uri "$env:MONGO_URI" `
  --database workhub `
  --confirm
```

The migration performs document upserts and does not clear the destination.

## Authentication

Login and registration return a time-limited JWT. Desktop requests send the
token using the standard `Authorization: Bearer ...` header. MongoDB
credentials remain only on the central server.

## Windows startup

From a terminal in the installed app folder:

```powershell
.\.venv\Scripts\python.exe desktop_app.py --install-startup
```

Remove startup:

```powershell
.\.venv\Scripts\python.exe desktop_app.py --uninstall-startup
```
