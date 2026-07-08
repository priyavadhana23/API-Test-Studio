# API Test Studio — Backend Docker Guide

The FastAPI backend runs as a self-contained Docker image.  
All Python dependencies are installed at build time; runtime data (database, reports, uploaded specs) is kept outside the image via volume mounts.

---

## Prerequisites

| Tool | Minimum version |
|---|---|
| Docker | 24.x |
| (Optional) Docker Compose | 2.x — for Phase 10.2 |

---

## Quick Start

```bash
# From the API_Test_Studio/ directory:

# 1. Build
docker build -t api-test-studio-backend .

# 2. Run (ephemeral — data lost on container stop)
docker run -p 8000:8000 api-test-studio-backend

# 3. Open Swagger UI
open http://localhost:8000/docs
```

---

## Persistent Data (Recommended)

Mount host directories over the container's data paths so data survives restarts:

```bash
docker run -p 8000:8000 \
  -v $(pwd)/database:/app/database \
  -v $(pwd)/reports:/app/reports \
  -v $(pwd)/uploaded_specs:/app/uploaded_specs \
  -v $(pwd)/history:/app/history \
  -v $(pwd)/logs:/app/logs \
  api-test-studio-backend
```

---

## Environment Variables

Copy `.env.example` to `.env` and adjust, then pass it to Docker:

```bash
cp .env.example .env
# Edit .env as needed

docker run -p 8000:8000 --env-file .env \
  -v $(pwd)/database:/app/database \
  api-test-studio-backend
```

### Full variable reference

| Variable | Default | Description |
|---|---|---|
| `BACKEND_HOST` | `0.0.0.0` | Bind address — must be `0.0.0.0` in Docker |
| `BACKEND_PORT` | `8000` | Uvicorn listen port |
| `BACKEND_RELOAD` | `false` | Hot-reload (dev only, never in production) |
| `LOG_LEVEL` | `info` | Log verbosity: `debug` / `info` / `warning` / `error` |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Comma-separated allowed origins |
| `API_ENVIRONMENT` | `development` | Active environment key from `environments.yaml` |
| `DATABASE_PATH` | `/app/database/api_test_studio.db` | SQLite file path inside container |
| `REPORTS_DIR` | `/app/reports` | Report output directory |
| `HISTORY_DIR` | `/app/history` | Execution history directory |
| `UPLOADED_SPECS_DIR` | `/app/uploaded_specs` | Uploaded spec storage |

---

## Endpoints

Once running, all endpoints are available at `http://localhost:8000`:

| URL | Description |
|---|---|
| `/docs` | Swagger UI (interactive) |
| `/redoc` | ReDoc (read-only docs) |
| `/openapi.json` | Raw OpenAPI schema |
| `/api/health` | Health probe — returns `{"status":"healthy"}` |
| `POST /api/specifications/upload` | Upload a spec file |
| `POST /api/jobs` | Submit an async test run |
| `GET /api/jobs/{job_id}` | Poll job status |
| `GET /api/runs` | List execution history |
| `GET /api/analytics/{run_id}` | Full analytics summary |
| `GET /api/reports/{run_id}` | List generated reports |

---

## Health Check

Docker runs this automatically every 30 seconds:

```
GET http://localhost:8000/api/health
→ {"status":"healthy", ...}
```

Check container health status manually:

```bash
docker inspect --format='{{.State.Health.Status}}' <container_id>
```

---

## Build Details

| Layer | Contents |
|---|---|
| Base | `python:3.12-slim` |
| OS packages | `gcc`, `libffi-dev`, `curl` |
| Python deps | All 37 packages from `requirements.txt` (pinned versions) |
| App source | All framework modules + FastAPI backend |
| Exposed port | `8000/tcp` |

---

## Troubleshooting

### Container exits immediately
```bash
docker logs <container_id>
```
Most common causes: missing `requirements.txt`, import error in a module.

### Health check failing
Ensure port `8000` is mapped (`-p 8000:8000`) and no other process is using it on the host.

### Database not persisting
Add the volume mount: `-v $(pwd)/database:/app/database`

### CORS errors from the React frontend
Add your frontend origin to `CORS_ORIGINS`:
```bash
-e CORS_ORIGINS="http://localhost:5173,http://your-frontend-host"
```

### Permission errors on volume mounts
The container runs as root by default. If your host files are owned by a different user, run:
```bash
docker run --user $(id -u):$(id -g) ...
```

---

## Example: Development Workflow

```bash
# Build once
docker build -t api-test-studio-backend .

# Run with live data and debug logging
docker run -p 8000:8000 \
  -e LOG_LEVEL=debug \
  -e BACKEND_RELOAD=false \
  -v $(pwd)/database:/app/database \
  -v $(pwd)/reports:/app/reports \
  -v $(pwd)/uploaded_specs:/app/uploaded_specs \
  --name ats-backend \
  api-test-studio-backend

# In another terminal — tail logs
docker logs -f ats-backend

# Stop
docker stop ats-backend && docker rm ats-backend
```

---

## Image Rebuild Trigger

The Dockerfile is structured so that changing only Python source files does **not** invalidate the `pip install` cache layer. Only changes to `requirements.txt` trigger a full dependency reinstall.

```
Layer 1  python:3.12-slim         (base)
Layer 2  apt-get install          (OS packages)
Layer 3  COPY requirements.txt    ← only invalidated by requirements change
Layer 4  pip install              ← only invalidated by requirements change
Layer 5  COPY source files        ← invalidated by any source change
```
