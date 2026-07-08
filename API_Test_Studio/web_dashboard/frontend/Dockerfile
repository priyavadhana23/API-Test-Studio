# =============================================================================
# API Test Studio — Frontend Dockerfile
# Multi-stage build: Node (build) → Nginx (runtime)
#
# Stage 1 compiles the React/TypeScript source with Vite and produces a
# static bundle in /app/dist.  Stage 2 copies that bundle into a minimal
# Nginx image; the Node toolchain is discarded and never ships.
#
# Build:
#   docker build -t api-test-studio-frontend .
#
# Run (backend already running on host port 8000):
#   docker run -p 80:80 \
#     -e VITE_API_BASE_URL=http://localhost:8000 \
#     api-test-studio-frontend
#
# With a custom backend URL (e.g. when both are in Docker):
#   docker run -p 80:80 \
#     -e VITE_API_BASE_URL=http://backend:8000 \
#     api-test-studio-frontend
# =============================================================================

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1 — Build
# ─────────────────────────────────────────────────────────────────────────────
FROM node:22-slim AS builder

# Build-time environment variable.
# VITE_API_BASE_URL is baked into the bundle at build time by Vite.
# Override with --build-arg VITE_API_BASE_URL=http://your-backend:8000
ARG VITE_API_BASE_URL=""
ARG VITE_APP_NAME="API Test Studio"
ARG VITE_APP_VERSION="1.0.0"

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_APP_NAME=${VITE_APP_NAME} \
    VITE_APP_VERSION=${VITE_APP_VERSION}

WORKDIR /app

# ── Install dependencies (cached layer — only reruns when lock file changes) ──
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

# ── Copy source and build ─────────────────────────────────────────────────────
COPY index.html        ./
COPY tsconfig.json     ./
COPY vite.config.ts    ./
COPY src/              ./src/

RUN npm run build
# Output is in /app/dist


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2 — Runtime (Nginx)
# ─────────────────────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

# Labels
LABEL maintainer="API Test Studio Team" \
      version="1.0.0" \
      description="API Test Studio — React Dashboard (Nginx)"

# Remove the default Nginx site
RUN rm /etc/nginx/conf.d/default.conf

# Copy our SPA-aware Nginx config
COPY nginx.conf /etc/nginx/conf.d/app.conf

# Copy the Vite production build from Stage 1
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx runs as root by default in the official image; that's fine for
# a container whose sole job is serving static files on port 80.
EXPOSE 80

# Healthcheck — Nginx serves the index page
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1

# Start Nginx in the foreground (required for Docker PID 1)
CMD ["nginx", "-g", "daemon off;"]
