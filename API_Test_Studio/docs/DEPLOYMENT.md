# Deployment Guide — API Test Studio

---

## Table of Contents

- [Docker Compose (Recommended)](#docker-compose-recommended)
- [Backend Standalone](#backend-standalone)
- [Frontend Standalone](#frontend-standalone)
- [Production Environment Variables](#production-environment-variables)
- [Persistent Data](#persistent-data)
- [Nginx Reverse Proxy (Advanced)](#nginx-reverse-proxy-advanced)
- [GitHub Actions CI/CD](#github-actions-cicd)
- [Production Recommendations](#production-recommendations)
- [Monitoring](#monitoring)

---

## Docker Compose (Recommended)

The fastest path to a running platform. Requires only Docker and Docker Compose.

```bash
# 1. Clone
git clone https://github.com/<YOUR_ORG>/api-testing-project.git
cd api-testing-project/API_Test_Studio

# 2. Configure
cp .env.docker.example .env
# Edit .env — at minimum review CORS_ORIGINS for your domain

# 3. Build and start
docker compose up --build -d

# 4. Verify
curl http://localhost:8000/api/health
curl -s -o /dev/null -w "%{http_code}" http://localhost:80/
```

### Startup order

```
1. ats-backend  starts → health check passes (~5 s)
2. ats-frontend starts → Nginx serves React SPA
```

### Stopping

```bash
docker compose down          # stop containers, keep data volumes
docker compose down -v       # stop containers AND delete all data (DESTRUCTIVE)
```

### Updating after code changes

```bash
docker compose build --no-cache
docker compose up -d
```

---

## Backend Standalone

### Local (venv)

```bash
cd API_Test_Studio
source .venv/bin/activate
uvicorn web_dashboard.backend.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1 \
  --log-level info
```

> Use `--workers 1` — the in-memory job store (`JobStore`) is not shared across multiple worker processes.

### Docker only

```bash
docker build -t api-test-studio-backend .

docker run -d \
  --name ats-backend \
  -p 8000:8000 \
  -e CORS_ORIGINS="http://your-frontend-domain" \
  -e LOG_LEVEL=info \
  -v $(pwd)/database:/app/database \
  -v $(pwd)/reports:/app/reports \
  -v $(pwd)/uploaded_specs:/app/uploaded_specs \
  --restart unless-stopped \
  api-test-studio-backend
```

---

## Frontend Standalone

The frontend must be built with the correct backend URL baked in:

```bash
cd web_dashboard/frontend

# Development build (Vite dev server)
npm run dev

# Production build pointing at a specific backend
docker build \
  --build-arg VITE_API_BASE_URL=https://api.your-domain.com \
  -t api-test-studio-frontend .

docker run -d \
  --name ats-frontend \
  -p 80:80 \
  --add-host=backend:host-gateway \
  --restart unless-stopped \
  api-test-studio-frontend
```

> `VITE_API_BASE_URL` is baked into the JS bundle at build time. If you leave it empty, Nginx handles routing to the backend via `proxy_pass http://backend:8000`.

---

## Production Environment Variables

### Backend

| Variable | Production value | Notes |
|---|---|---|
| `BACKEND_HOST` | `0.0.0.0` | Required in Docker |
| `BACKEND_PORT` | `8000` | Match your port mapping |
| `BACKEND_RELOAD` | `false` | Never `true` in production |
| `LOG_LEVEL` | `warning` | Reduce noise in production |
| `CORS_ORIGINS` | `https://your-domain.com` | Restrict to your actual domain |
| `API_ENVIRONMENT` | `production` | Use the production environment config |

### Frontend build args

| Variable | Production value | Notes |
|---|---|---|
| `VITE_API_BASE_URL` | `""` (empty) | Nginx proxies internally |
| `VITE_APP_NAME` | `API Test Studio` | |
| `VITE_APP_VERSION` | `1.0.0` | Match your release tag |

---

## Persistent Data

All mutable data lives in Docker named volumes or host-mounted directories.

| Path in container | Volume name | Contents | Backup priority |
|---|---|---|---|
| `/app/database` | `ats-database` | SQLite `.db` file | **Critical** |
| `/app/uploaded_specs` | `ats-uploaded-specs` | Spec YAML/JSON files | High |
| `/app/reports` | `ats-reports` | HTML, PDF, CSV, JSON reports | Medium |
| `/app/history` | `ats-history` | Run export files | Low |
| `/app/logs` | `ats-logs` | Application logs | Low |

### Backup

```bash
# Backup the SQLite database
docker run --rm \
  -v ats-database:/data \
  -v $(pwd)/backups:/backup \
  alpine cp /data/api_test_studio.db /backup/api_test_studio_$(date +%Y%m%d).db

# Restore
docker run --rm \
  -v ats-database:/data \
  -v $(pwd)/backups:/backup \
  alpine cp /backup/api_test_studio_20260708.db /data/api_test_studio.db
```

---

## Nginx Reverse Proxy (Advanced)

To put both services behind a single domain with TLS:

```nginx
# /etc/nginx/conf.d/api-test-studio.conf
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Frontend
    location / {
        proxy_pass http://localhost:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Backend (accessed directly if needed)
    location /api-direct/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
    }
}
```

> The frontend's Nginx container already proxies `/api/*` to the backend internally — you only need the outer proxy for TLS termination.

---

## GitHub Actions CI/CD

The CI pipeline runs on every push to `main`, `master`, and `develop`.

```yaml
# Trigger
on:
  push:
    branches: [main, master, develop]
  pull_request:
    branches: [main, master, develop]
  workflow_dispatch:
```

### Jobs

| Job | What it does | Time |
|---|---|---|
| `backend` | Python imports, FastAPI startup, schema validation | ~2 min |
| `frontend` | npm ci, TypeScript check, production build | ~3 min |
| `docker` | Compose syntax, backend image build + smoke test, frontend image build + nginx -t | ~8 min |
| `ci-gate` | Fails if any upstream job failed | <10 s |

### Artifacts uploaded per run

| Artifact | Retention |
|---|---|
| `backend-verification-<N>` | 30 days |
| `frontend-dist-<N>` | 7 days |

### Required secrets

None — the CI pipeline does not push images or deploy anywhere. If you add deployment steps, add:

| Secret | Usage |
|---|---|
| `DOCKER_USERNAME` | Docker Hub push |
| `DOCKER_PASSWORD` | Docker Hub push |

---

## Production Recommendations

| Concern | Recommendation |
|---|---|
| **Workers** | Keep `--workers 1` — `JobStore` is process-local. For multi-worker, replace with Redis + Celery. |
| **TLS** | Put the platform behind Nginx + Let's Encrypt. Never expose port 8000 directly. |
| **Database** | SQLite is suitable for single-server deployments. For horizontal scaling, migrate to PostgreSQL via SQLAlchemy. |
| **File storage** | Mount `uploaded_specs` and `reports` to a cloud object store (S3, GCS) for persistence across container rebuilds. |
| **Health monitoring** | Configure an uptime monitor to poll `GET /api/health` every 60 s. |
| **Log aggregation** | Mount `/app/logs` or stream container logs to a log aggregator (Datadog, CloudWatch, Loki). |
| **Resource limits** | Set `mem_limit: 1g` in `docker-compose.yml` for the backend to prevent runaway report generation. |
| **CORS** | In production, set `CORS_ORIGINS` to your exact frontend domain — not `*`. |

---

## Monitoring

### Health check endpoint

```bash
# Returns 200 when all components are ready
curl http://localhost:8000/api/health

# Example cron monitor
*/5 * * * * curl -sf http://localhost:8000/api/health > /dev/null || alert
```

### Docker health status

```bash
docker inspect ats-backend  --format "{{.State.Health.Status}}"
docker inspect ats-frontend --format "{{.State.Health.Status}}"
```

### Log tailing

```bash
docker compose logs -f backend    # FastAPI + access log
docker compose logs -f frontend   # Nginx access + error log
```
