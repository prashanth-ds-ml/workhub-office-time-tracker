# WorkHub for Windows

## Install and run

1. Extract the complete `WorkHub-Installer.zip` archive.
2. Double-click `Install WorkHub.bat`.
3. The installer copies WorkHub and its bundled runtime dependencies, then
   creates Desktop and Start menu shortcuts.
4. Choose Register as Admin or Register as User.
5. Admin registration requires the private bootstrap key.

Python and pip are not required on employee computers. Do not move
`Install WorkHub.bat` out of the extracted installer folder before running it.
The installer configures the current hosted WorkHub API automatically.

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
4. Set `WORKHUB_BOOTSTRAP_SECRET`. Anyone registering as Admin must enter this
   private value in the registration page.
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

The current deployment uses Render Free. It sleeps when idle and can take up
to approximately 90 seconds to wake. The desktop client handles this with a
wake status, retry window, and office-hours heartbeat.

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

The installed executable can manage its Windows startup entry directly:

```powershell
& "$env:LOCALAPPDATA\WorkHubApp\WorkHub.exe" --install-startup
```

Remove startup:

```powershell
& "$env:LOCALAPPDATA\WorkHubApp\WorkHub.exe" --uninstall-startup
```
