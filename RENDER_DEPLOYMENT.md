# Deploy WorkHub Web and API on the Existing Render Service

## Current services

- Existing Render Web Service for both React and FastAPI
- MongoDB Atlas

## Render environment variables

| Key | Value |
|---|---|
| `WORKHUB_ENV` | `production` |
| `MONGO_URI` | MongoDB Atlas connection string |
| `MONGO_DB` | `workhub` |
| `WORKHUB_JWT_SECRET` | Long random secret |
| `WORKHUB_JWT_EXPIRE_HOURS` | `12` |
| `WORKHUB_BOOTSTRAP_SECRET` | Private key required for Admin registration |
| `WORKHUB_ALLOW_SELF_REGISTRATION` | `true` or `false` |
| `WORKHUB_EMAIL_DOMAIN` | `sims.healthcare` |

## Blueprint deployment

The repository `render.yaml` keeps the existing `workhub-api` service. Its
build command installs Python dependencies, builds React, and then FastAPI
serves both products from the existing URL.

Sync the existing Blueprint or update its build command to:

```text
pip install -r requirements.txt && cd web_app && npm ci && npm run build
```

Current API:

```text
https://workhub-api-u07x.onrender.com
```

The Free service sleeps after inactivity. The first page request can take about
30–90 seconds while it wakes. Upgrading this existing service to an always-on
instance eliminates that cold-start delay.

After deployment, verify:

```text
https://YOUR-SERVICE.onrender.com/health
```

The response must report:

- `status: ok`
- `environment: production`
- `storage.backend: mongo`
- `storage.connected: true`

The same URL now serves:

- `/` and browser routes: React application
- `/docs`: API documentation
- `/health`: service and MongoDB health
- Existing API endpoints used by desktop clients

The browser uses same-origin HTTP-only session cookies. Bearer-token support
remains unchanged for the Python desktop application.
