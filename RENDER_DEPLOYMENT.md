# Deploy WorkHub API on Render

## Recommended services

- Render Starter Web Service
- MongoDB Atlas
- WorkHub desktop clients configured with the Render HTTPS URL

## Render environment variables

| Key | Value |
|---|---|
| `WORKHUB_ENV` | `production` |
| `MONGO_URI` | MongoDB Atlas connection string |
| `MONGO_DB` | `workhub` |
| `WORKHUB_JWT_SECRET` | Long random secret |
| `WORKHUB_JWT_EXPIRE_HOURS` | `12` |
| `WORKHUB_BOOTSTRAP_SECRET` | Private first-admin setup code |
| `WORKHUB_ALLOW_SELF_REGISTRATION` | `true` or `false` |

## Render service configuration

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`
- Instance: Starter or higher

After deployment, verify:

```text
https://YOUR-SERVICE.onrender.com/health
```

The response must report:

- `status: ok`
- `environment: production`
- `storage.backend: mongo`
- `storage.connected: true`

Use the same Render URL during every desktop-client installation.
