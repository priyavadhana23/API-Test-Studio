# API Test Studio — Frontend Docker Guide

The React dashboard is packaged as a two-stage Docker image:

| Stage | Base image | Purpose |
|---|---|---|
| `builder` | `node:22-slim` | TypeScript compilation + Vite production build |
| `runtime` | `nginx:1.27-alpine` | Serve static files, proxy `/api/*` to the backend |

The Node toolchain is completely absent from the final image — only the compiled static assets and Nginx are shipped.

---

## Prerequisites

| Tool | Minimum version |
|---|---|
| Docker | 24.x |
| Running backend | Phase 10.1 image (`api-test-studio-backend`) or any FastAPI server on port 8000 |

---

## Quick Start

```bash
# From web_dashboard/frontend/

# 1. Build (backend assumed at localhost:8000)
docker build -t api-test-studio-frontend .

# 2. Run
docker run -p 80:80 api-test-studio-frontend

# 3. Open
open http://localhost
```

---

## Pointing to a Different Backend

Vite bakes `VITE_API_BASE_URL` into the bundle at **build time**.  
Pass it as a build argument:

```bash
docker build \
  --build-arg VITE_API_BASE_URL=http://your-backend-host:8000 \
  -t api-test-studio-frontend \
  .
```

The Nginx config also proxies `/api/*` to `http://backend:8000` at runtime.  
In standalone Docker (without Compose) you have two options:

**Option A — host network (simplest for local dev):**
```bash
docker run --network host api-test-studio-frontend
# Nginx proxies /api/* → http://backend:8000 using the host network
```

**Option B — explicit IP:**
```bash
# Find your host IP
HOST_IP=$(ipconfig getifaddr en0)   # macOS
# HOST_IP=$(hostname -I | awk '{print $1}')  # Linux

docker build \
  --build-arg VITE_API_BASE_URL=http://${HOST_IP}:8000 \
  -t api-test-studio-frontend .

docker run -p 80:80 api-test-studio-frontend
```

---

## Build Arguments

| Argument | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `""` (empty) | Backend origin baked into the JS bundle |
| `VITE_APP_NAME` | `API Test Studio` | App name shown in the UI |
| `VITE_APP_VERSION` | `1.0.0` | Version shown in the app bar |

---

## How Nginx Serves the SPA

```
Browser: GET /runs/abc123
  → Nginx: no file named "runs/abc123" in /usr/share/nginx/html
  → try_files $uri $uri/ /index.html
  → serves index.html
  → React Router takes over and renders the RunDetailPage
```

All routes (`/dashboard`, `/upload`, `/runs/:id`, `/analytics`) work
correctly on direct navigation and page refresh.

---

## API Proxying

In the production Docker image the Vite dev-server proxy is gone.  
Nginx takes over:

```nginx
location /api/ {
    proxy_pass http://backend:8000;
    ...
}
```

`backend` resolves to the FastAPI container when using Docker Compose
(Phase 10.3).  For standalone use, replace `backend` with the actual
backend host or pass the network flag shown above.

---

## Ports

| Port | Protocol | Description |
|---|---|---|
| `80` | HTTP | Nginx web server (map with `-p 80:80` or `-p <host>:80`) |

---

## Static Asset Caching

Vite fingerprints every JS/CSS chunk with a content hash
(e.g. `react-vendor-BpY0uTVr.js`).  
Nginx sets `Cache-Control: public, immutable` with a 1-year expiry on
all fingerprinted assets.  `index.html` is never cached.

---

## Security Headers

Every response includes:

| Header | Value |
|---|---|
| `X-Frame-Options` | `SAMEORIGIN` |
| `X-Content-Type-Options` | `nosniff` |
| `X-XSS-Protection` | `1; mode=block` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |

---

## Troubleshooting

### Page refresh returns 404
Nginx `try_files` is not applied.  
Confirm `nginx.conf` is in `/etc/nginx/conf.d/app.conf` inside the container:
```bash
docker exec <container_id> cat /etc/nginx/conf.d/app.conf
```

### API calls fail (CORS / 502)
Nginx cannot reach the backend.  
- Check the backend is running and healthy.
- Use `--network host` or verify the `proxy_pass` hostname resolves.

### Build fails: TypeScript errors
Run locally first:
```bash
cd web_dashboard/frontend
npm run typecheck
```

### Blank white page
Open browser devtools → Console.  
Usually means `VITE_API_BASE_URL` is wrong or the backend is unreachable.

---

## Example: Full Build + Run Sequence

```bash
# From the API_Test_Studio/ directory:

# 1. Start the backend
docker run -d --name ats-backend -p 8000:8000 \
  -v $(pwd)/database:/app/database \
  api-test-studio-backend

# 2. Build frontend (backend reachable at localhost:8000)
cd web_dashboard/frontend
docker build \
  --build-arg VITE_API_BASE_URL=http://localhost:8000 \
  -t api-test-studio-frontend .

# 3. Run frontend
docker run -d --name ats-frontend -p 80:80 \
  api-test-studio-frontend

# 4. Open
open http://localhost
```

---

## Image Details

| Property | Value |
|---|---|
| Final base | `nginx:1.27-alpine` |
| Build base | `node:22-slim` (discarded) |
| Web root | `/usr/share/nginx/html` |
| Config | `/etc/nginx/conf.d/app.conf` |
| Exposed port | `80/tcp` |
