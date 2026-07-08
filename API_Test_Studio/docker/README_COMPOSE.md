# API Test Studio — Docker Compose Guide

Docker Compose orchestrates the complete platform with a single command.

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Network: ats-network             │
│                                                             │
│  ┌──────────────────────┐     ┌──────────────────────────┐  │
│  │  frontend (Nginx)    │────▶│  backend (FastAPI)       │  │
│  │  port 80             │     │  port 8000               │  │
│  │                      │     │                          │  │
│  │  Serves React SPA    │     │  REST API + Pipeline     │  │
│  │  Proxies /api/* ──── ┼────▶│  /api/health             │  │
│  │  to backend:8000     │     │  /api/runs               │  │
│  └──────────────────────┘     │  /api/jobs               │  │
│           │                   │  /api/analytics          │  │
│           │                   │  /api/reports            │  │
│  Host     │                   └──────────┬───────────────┘  │
│  :80      │                              │                  │
└───────────┼──────────────────────────────┼──────────────────┘
            │ Browser                      │ Named volumes
            ▼                              ▼
    http://localhost          ats-database
                              ats-uploaded-specs
                              ats-reports
                              ats-history
                              ats-logs
```

---

## Prerequisites

| Tool | Minimum version |
|---|---|
| Docker | 24.x |
| Docker Compose | v2 (included with Docker Desktop) |

Verify:
```bash
docker compose version
```

---

## Quick Start

```bash
# From the API_Test_Studio/ directory:

# 1. Copy the example env file
cp .env.docker.example .env

# 2. Build images and start all services
docker compose up --build

# 3. Open the dashboard
open http://localhost

# 4. Open the API docs
open http://localhost:8000/docs
```

The terminal will show live logs from both containers.  
Press `Ctrl+C` to stop.

---

## Start in Background (Detached)

```bash
docker compose up --build -d

# Check everything is running
docker compose ps

# Tail logs
docker compose logs -f
docker compose logs -f backend
docker compose logs -f frontend
```

---

## Stop and Restart

```bash
# Stop containers — data volumes are kept
docker compose down

# Restart (uses existing images — no rebuild)
docker compose up -d

# Restart with a rebuild (e.g. after code changes)
docker compose up --build -d
```

---

## Wipe All Data

```bash
# Stop AND remove all named volumes — ALL DATA IS LOST
docker compose down -v
```

---

## Service Details

### Backend (`ats-backend`)

| Property | Value |
|---|---|
| Image | `api-test-studio-backend` |
| Build context | `API_Test_Studio/` (root `Dockerfile`) |
| Internal port | `8000` |
| Host port | `${BACKEND_PORT:-8000}` |
| Health check | `GET /api/health` every 30 s |
| Restart | `unless-stopped` |

### Frontend (`ats-frontend`)

| Property | Value |
|---|---|
| Image | `api-test-studio-frontend` |
| Build context | `web_dashboard/frontend/` |
| Internal port | `80` |
| Host port | `${FRONTEND_PORT:-80}` |
| Depends on | `backend` (waits for healthy status) |
| Restart | `unless-stopped` |

---

## Container Startup Order

```
1. backend starts
       ↓
2. Docker runs healthcheck: GET /api/health
       ↓ (passes after ~5 s)
3. frontend starts (depends_on: backend: condition: service_healthy)
       ↓
4. Nginx begins serving React SPA
       ↓
5. Platform is ready
```

If `backend` fails its health check `frontend` will not start.

---

## Network

| Property | Value |
|---|---|
| Network name | `ats-network` |
| Driver | `bridge` |
| Backend hostname | `backend` (resolved by Nginx `proxy_pass`) |
| Frontend hostname | `frontend` |

The Nginx config inside the frontend container proxies all `/api/*` requests to `http://backend:8000`. The browser never talks directly to the backend — everything goes through Nginx on port 80.

---

## Named Volumes

| Volume name | Container path | Contents |
|---|---|---|
| `ats-database` | `/app/database` | SQLite database (`api_test_studio.db`) |
| `ats-uploaded-specs` | `/app/uploaded_specs` | Uploaded Swagger/OpenAPI files |
| `ats-reports` | `/app/reports` | Generated HTML/PDF/CSV/JSON reports |
| `ats-history` | `/app/history` | Run export files |
| `ats-logs` | `/app/logs` | Application log files |

Inspect volumes:
```bash
docker volume ls | grep ats-
docker volume inspect ats-database
```

---

## Environment Variables

| Variable | Default | Where used |
|---|---|---|
| `BACKEND_PORT` | `8000` | Host port for backend |
| `FRONTEND_PORT` | `80` | Host port for frontend |
| `LOG_LEVEL` | `info` | Uvicorn + app logging |
| `API_ENVIRONMENT` | `development` | Active environment from `environments.yaml` |
| `VITE_API_BASE_URL` | `""` (empty) | Baked into JS bundle (Nginx handles routing) |
| `VITE_APP_NAME` | `API Test Studio` | App title in UI |
| `VITE_APP_VERSION` | `1.0.0` | Version shown in app bar |

---

## Useful Commands

```bash
# View running containers and their status
docker compose ps

# Live logs (all services)
docker compose logs -f

# Backend logs only
docker compose logs -f backend

# Frontend logs only
docker compose logs -f frontend

# Open a shell inside the backend container
docker compose exec backend bash

# Check backend health manually
curl http://localhost:8000/api/health

# Rebuild only one service
docker compose build backend
docker compose build frontend

# Restart only one service
docker compose restart backend

# List all volumes
docker volume ls | grep ats-

# Inspect the database volume location on host
docker volume inspect ats-database
```

---

## Troubleshooting

### `frontend` exits immediately / "backend not healthy"
The backend healthcheck failed.  Check backend logs:
```bash
docker compose logs backend
```
Common cause: port 8000 already in use on the host.  
Change `BACKEND_PORT=8001` in `.env` and rebuild.

### 502 Bad Gateway from Nginx
Nginx cannot reach the backend.  Verify both containers are on `ats-network`:
```bash
docker network inspect ats-network
```

### API calls fail from the browser
Open browser devtools → Network tab.  
All `/api/*` calls should go to `http://localhost:80/api/` (Nginx), not directly to port 8000.  
If `VITE_API_BASE_URL` was set to a wrong value during build, rebuild:
```bash
docker compose build --no-cache frontend
docker compose up -d frontend
```

### Database not persisting
Confirm `ats-database` volume exists:
```bash
docker volume inspect ats-database
```
Never use `docker compose down -v` unless you intend to wipe data.

### Port 80 already in use
Set `FRONTEND_PORT=8080` in `.env`:
```bash
echo "FRONTEND_PORT=8080" >> .env
docker compose up -d
# Dashboard → http://localhost:8080
```

### Rebuild after source changes
```bash
docker compose build --no-cache
docker compose up -d
```
