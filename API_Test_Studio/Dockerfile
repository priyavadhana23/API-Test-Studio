# =============================================================================
# API Test Studio — Backend Dockerfile
# =============================================================================
# Multi-stage-friendly single-stage production image.
#
# Build:
#   docker build -t api-test-studio-backend .
#
# Run:
#   docker run -p 8000:8000 api-test-studio-backend
#
# Run with persistent data volumes:
#   docker run -p 8000:8000 \
#     -v $(pwd)/database:/app/database \
#     -v $(pwd)/reports:/app/reports   \
#     -v $(pwd)/uploaded_specs:/app/uploaded_specs \
#     api-test-studio-backend
# =============================================================================

# ── Base image ────────────────────────────────────────────────────────────────
# Python 3.12 slim: smaller footprint than the full image, still has gcc for
# compiled wheels (Pillow, reportlab, pydantic-core).
FROM python:3.12-slim

# ── Build-time labels ─────────────────────────────────────────────────────────
LABEL maintainer="API Test Studio Team" \
      version="1.0.0" \
      description="API Test Studio — Enterprise API Testing Platform (Backend)"

# ── OS-level dependencies ─────────────────────────────────────────────────────
# gcc / libpq-dev are needed by some compiled wheels (Pillow, reportlab).
# curl is included for healthcheck. Clean apt cache in the same layer.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies (separate layer for cache efficiency) ─────────
# Copy requirements first so Docker reuses this layer on code-only changes.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── Copy application source ───────────────────────────────────────────────────
# Framework modules
COPY analytics/          ./analytics/
COPY api_parser/         ./api_parser/
COPY configs/            ./configs/
COPY constants/          ./constants/
COPY database/           ./database/
COPY exceptions/         ./exceptions/
COPY executor/           ./executor/
COPY interfaces/         ./interfaces/
COPY models/             ./models/
COPY reporting/          ./reporting/
COPY schemas/            ./schemas/
COPY templates/          ./templates/
COPY testcase_generator/ ./testcase_generator/
COPY utilities/          ./utilities/
COPY validators/         ./validators/

# Web dashboard backend
COPY web_dashboard/      ./web_dashboard/

# Top-level entry points and configuration
COPY app.py              ./app.py
COPY requirements.txt    ./requirements.txt

# ── Runtime directories ───────────────────────────────────────────────────────
# Pre-create mutable directories so volume mounts work with the correct owner.
# These are writable by the container process at runtime.
RUN mkdir -p \
        /app/database \
        /app/reports \
        /app/uploaded_specs \
        /app/history \
        /app/logs \
        /app/assets

# ── Expose port ───────────────────────────────────────────────────────────────
EXPOSE 8000

# ── Health check ──────────────────────────────────────────────────────────────
# Docker will mark the container unhealthy if /api/health returns non-2xx.
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# ── Default environment variables ─────────────────────────────────────────────
# BACKEND_HOST must be 0.0.0.0 inside Docker so the port is reachable from
# outside the container. Override any of these via -e or an .env file.
ENV BACKEND_HOST=0.0.0.0 \
    BACKEND_PORT=8000 \
    BACKEND_RELOAD=false \
    LOG_LEVEL=info \
    CORS_ORIGINS="http://localhost:5173,http://localhost:3000,http://localhost:8080"

# ── Start command ─────────────────────────────────────────────────────────────
# Run uvicorn directly — no shell wrapper needed.
# web_dashboard.backend.main resolves correctly because /app is the WORKDIR
# and all framework packages are on sys.path (handled inside settings.py).
CMD ["uvicorn", "web_dashboard.backend.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--log-level", "info"]
