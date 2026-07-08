# Installation Guide — API Test Studio

Three installation paths are supported. Choose the one that fits your needs.

| Path | Best for |
|---|---|
| [Local (venv)](#local-installation) | Development, debugging, contributing |
| [Docker (individual)](#docker-installation) | Testing the backend or frontend in isolation |
| [Docker Compose](#docker-compose-recommended) | Running the complete platform — recommended |

---

## Prerequisites

| Tool | Minimum | Install |
|---|---|---|
| Python | 3.12 | [python.org](https://www.python.org/downloads/) |
| Node.js | 22 LTS | [nodejs.org](https://nodejs.org/) |
| Docker | 24 | [docs.docker.com](https://docs.docker.com/get-docker/) |
| Docker Compose | v2 (included with Docker Desktop) | included above |
| Git | any | [git-scm.com](https://git-scm.com/) |

---

## Local Installation

### 1. Clone the repository

```bash
git clone https://github.com/<YOUR_ORG>/api-testing-project.git
cd api-testing-project/API_Test_Studio
```

### 2. Create a Python virtual environment

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

All 37 packages are pinned to exact versions. Installation takes approximately 60 seconds.

### 4. Verify the backend

```bash
python -c "
import sys; sys.path.insert(0, '.')
from web_dashboard.backend.main import app
s = app.openapi()
n = sum(len(v) for v in s['paths'].values())
print(f'Backend OK — {n} endpoints')
"
# Expected: Backend OK — 19 endpoints
```

### 5. Start the backend

```bash
uvicorn web_dashboard.backend.main:app --reload --port 8000
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for the Swagger UI.

### 6. Install frontend dependencies

```bash
cd web_dashboard/frontend
npm install
```

### 7. Start the frontend

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) for the React dashboard.

> The Vite dev server proxies all `/api/*` requests to `http://127.0.0.1:8000` automatically — no CORS configuration needed.

### 8. (Optional) Run the CLI pipeline

Drop a spec file into `uploaded_specs/` and run:

```bash
cd API_Test_Studio
python app.py
```

This runs all 8 phases headlessly and writes reports to `reports/`.

---

## Configuration

### Environment selection

Edit `configs/environments.yaml` to configure your target API:

```yaml
environments:
  development:
    name: Development
    base_url: "https://your-api.example.com"
    auth_type: "bearer"
    auth_token: "your-token-here"
```

Set the active environment in `configs/config.yaml`:

```yaml
active_environment: development
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `BACKEND_HOST` | `127.0.0.1` | Uvicorn bind address |
| `BACKEND_PORT` | `8000` | Uvicorn port |
| `CORS_ORIGINS` | localhost origins | Comma-separated allowed origins |
| `LOG_LEVEL` | `info` | Log verbosity |
| `API_ENVIRONMENT` | `development` | Active config environment |

---

## Docker Installation

### Backend only

```bash
# From API_Test_Studio/
docker build -t api-test-studio-backend .

# Ephemeral (data lost on container stop)
docker run -p 8000:8000 api-test-studio-backend

# With persistent volumes
docker run -p 8000:8000 \
  -v $(pwd)/database:/app/database \
  -v $(pwd)/reports:/app/reports \
  -v $(pwd)/uploaded_specs:/app/uploaded_specs \
  api-test-studio-backend
```

### Frontend only

```bash
# From web_dashboard/frontend/
docker build -t api-test-studio-frontend .

docker run -p 80:80 \
  --add-host=backend:host-gateway \
  api-test-studio-frontend
```

See [`docker/README_BACKEND.md`](../docker/README_BACKEND.md) and [`docker/README_FRONTEND.md`](../docker/README_FRONTEND.md) for full options.

---

## Docker Compose (Recommended)

The quickest way to run the complete platform.

### 1. Copy the environment file

```bash
cp .env.docker.example .env
```

### 2. (Optional) Edit `.env`

```bash
# Change ports if 80 or 8000 are already in use
FRONTEND_PORT=8080
BACKEND_PORT=8001
```

### 3. Build and start

```bash
docker compose up --build
```

First run takes 3–5 minutes (downloading base images + installing dependencies).  
Subsequent starts take under 10 seconds.

### 4. Access the platform

| Service | URL |
|---|---|
| Dashboard | [http://localhost](http://localhost) |
| API docs | [http://localhost:8000/docs](http://localhost:8000/docs) |
| API health | [http://localhost:8000/api/health](http://localhost:8000/api/health) |

### 5. Stop

```bash
# Stop containers — named volumes (data) are preserved
docker compose down

# Restart without rebuilding
docker compose up -d
```

---

## Verifying the Installation

Run this checklist after any installation method:

```bash
# 1. Backend health
curl http://localhost:8000/api/health
# Expected: {"status":"healthy", ...}

# 2. List uploaded specs
curl http://localhost:8000/api/specifications
# Expected: {"total": N, "specifications": [...]}

# 3. Frontend loads
curl -s -o /dev/null -w "%{http_code}" http://localhost:80/
# Expected: 200

# 4. API via Nginx proxy
curl http://localhost/api/health
# Expected: {"status":"healthy", ...}
```

---

## Troubleshooting

### `ModuleNotFoundError` after pip install

```bash
# Ensure you are in the activated virtual environment
which python   # should point to .venv/bin/python

# Reinstall
pip install --force-reinstall -r requirements.txt
```

### Port already in use

```bash
# Find what is using port 8000
lsof -i :8000        # macOS/Linux
netstat -ano | findstr :8000   # Windows

# Use a different port
uvicorn web_dashboard.backend.main:app --port 8001
```

### Docker: `permission denied` on volumes

```bash
docker run --user $(id -u):$(id -g) ...
```

### Frontend: blank page after build

Check the browser console. Usually caused by `VITE_API_BASE_URL` being set to a wrong value at build time.

```bash
# Rebuild with the correct backend URL
docker build --build-arg VITE_API_BASE_URL=http://localhost:8000 .
```

### Docker Compose: frontend won't start

The frontend waits for the backend healthcheck to pass. Check backend logs:

```bash
docker compose logs backend
```

Common cause: missing `requirements.txt` or a Python import error.
