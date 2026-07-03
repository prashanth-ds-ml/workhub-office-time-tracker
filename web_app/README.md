# WorkHub React Web App

Modern browser interface for the existing WorkHub FastAPI backend.

## Run locally

```powershell
cd web_app
npm install
npm run dev
```

The app uses the current domain for API requests by default. This is the
production configuration because FastAPI serves the React build. To use a
separate backend during development, set `VITE_API_URL` in `.env`.

The browser UI is the primary employee and admin surface. It reads its public
settings from `/web/config`, including the allowed company email domain and
password recovery policy.

## Build

```powershell
npm run build
```

Static production files are generated in `web_app/dist`.

## Beta status

This surface is ready for a small monitored employee beta. Use the built-in
tests and the root smoke checks before rollout changes.
The login screen exposes password recovery again, and admin calendar dates are
normalized before save so common date-entry formats do not fail validation.

## Performance design

- FastAPI serves the compiled React application and existing API from one URL.
- Initial authenticated data uses one `/web/bootstrap` request.
- The most recent workspace snapshot is shown immediately from session cache
  while fresh data loads.
- Hashed JS/CSS assets use one-year immutable browser caching.
- API responses larger than 1 KB are gzip compressed.
- MongoDB-backed server caches use a short consistency window to avoid
  repeating ten collection reads for rapid consecutive actions.
