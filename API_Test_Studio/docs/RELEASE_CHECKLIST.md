# Release Checklist — API Test Studio

Use this checklist before tagging a new release or publishing the repository publicly.

---

## 1. Repository Cleanup

- [ ] Remove all `_check_*.py`, `_verify_*.py`, `_audit_*.py`, `_test_startup.py` files
- [ ] Remove any `tempCodeRunnerFile.py` or scratch files
- [ ] Ensure `__pycache__/` is in `.gitignore` and not committed
- [ ] Ensure `.venv/` is in `.gitignore` and not committed
- [ ] Ensure `node_modules/` is in `.gitignore` and not committed
- [ ] Ensure `database/*.db` is in `.gitignore` (or only the schema, not real data)
- [ ] Ensure `reports/`, `history/`, `logs/` are in `.gitignore`
- [ ] Ensure `.env` is in `.gitignore` (`.env.example` should be committed)
- [ ] No real API keys, tokens, or credentials in any committed file

---

## 2. Code Quality

- [ ] `npm run typecheck` passes with **0 errors**
- [ ] `npm run build` produces a clean production bundle
- [ ] `python -m py_compile app.py` and all module files compile without errors
- [ ] All framework imports succeed: `python -c "from web_dashboard.backend.main import app"`
- [ ] `docker compose config` validates without errors
- [ ] CI pipeline passes on the target branch

---

## 3. Documentation

- [ ] `README.md` — updated with correct badge URLs (`<YOUR_ORG>` replaced)
- [ ] `README.md` — screenshots added to `docs/screenshots/`
- [ ] `docs/ARCHITECTURE.md` — Mermaid diagrams render correctly on GitHub
- [ ] `docs/INSTALLATION.md` — all commands tested and accurate
- [ ] `docs/API_REFERENCE.md` — all 19 endpoints documented
- [ ] `docs/USER_GUIDE.md` — complete workflow walkthrough
- [ ] `docs/DEVELOPER_GUIDE.md` — extension guides verified
- [ ] `docs/DEPLOYMENT.md` — deployment steps tested
- [ ] All internal document links (`[text](path)`) resolve correctly
- [ ] `docker/README_BACKEND.md` — accurate
- [ ] `docker/README_FRONTEND.md` — accurate
- [ ] `docker/README_COMPOSE.md` — accurate

---

## 4. Docker Verification

- [ ] `docker build -t api-test-studio-backend .` succeeds
- [ ] `docker build -t api-test-studio-frontend ./web_dashboard/frontend/` succeeds
- [ ] `docker compose up --build` starts both containers cleanly
- [ ] `curl http://localhost:8000/api/health` returns `{"status":"healthy"}`
- [ ] `curl http://localhost/` returns HTTP 200
- [ ] `curl http://localhost/api/health` returns `{"status":"healthy"}` (Nginx proxy)
- [ ] All SPA routes return 200 on direct navigation: `/dashboard`, `/runs`, `/upload`, `/analytics`
- [ ] `docker compose down && docker compose up` — data persists

---

## 5. Frontend Verification

- [ ] Dashboard loads and displays summary cards
- [ ] Recent runs table is populated (if runs exist)
- [ ] Upload page — drag and drop works
- [ ] Upload page — file validation rejects non-spec files
- [ ] Runs page — search and filter work
- [ ] Run Details page — all sections render (charts, validator table, recommendations)
- [ ] Analytics page — run selector populated, all analytics sections show
- [ ] No JavaScript console errors
- [ ] No TypeScript errors (`npm run typecheck`)

---

## 6. Backend Verification

- [ ] All 19 endpoints appear in `/docs` Swagger UI
- [ ] `GET /api/health` — all three components `available: true`
- [ ] `POST /api/specifications/upload` — accepts YAML and JSON
- [ ] `POST /api/jobs` — returns `202` and a `job_id`
- [ ] `GET /api/jobs/{job_id}` — returns correct status progression
- [ ] `GET /api/runs` — returns paginated history
- [ ] `GET /api/analytics/{run_id}` — returns full `AnalyticsSummary`
- [ ] `GET /api/reports/{run_id}` — returns correct file list

---

## 7. End-to-End Test

- [ ] Upload `httpbin_verification.yaml` via the dashboard
- [ ] Set base URL override to `https://httpbin.org`
- [ ] Execute pipeline — progress screen shows all steps
- [ ] Completion screen shows run ID, pass %, test count
- [ ] "View Run" navigates to Run Details with correct data
- [ ] "View Analytics" shows health score, response time stats, endpoint table
- [ ] Reports are generated and downloadable via API
- [ ] New run appears in the Runs page history

---

## 8. Versioning & Git Tag

```bash
# Confirm you are on the main branch
git status

# Create an annotated release tag
git tag -a v1.0.0 -m "Phase 10.5 — Production Release"

# Push the tag
git push origin v1.0.0
```

---

## 9. GitHub Repository Settings

- [ ] Repository description set: `Enterprise API Testing Platform — specification-driven, fully automated`
- [ ] Topics added: `api-testing`, `python`, `fastapi`, `react`, `typescript`, `docker`, `openapi`, `swagger`, `automation`, `analytics`
- [ ] Repository visibility set correctly (public for portfolio)
- [ ] Default branch set to `main`
- [ ] Branch protection on `main` — require CI to pass before merging
- [ ] GitHub Actions badge URL updated in `README.md`

---

## 10. Screenshots

Capture and add to `docs/screenshots/`:

| Filename | Page to capture |
|---|---|
| `dashboard.png` | Dashboard with summary cards + recent runs |
| `upload.png` | Upload page — file selected + execution options |
| `progress.png` | Execution progress screen |
| `run-details.png` | Run Details — charts + validator table |
| `analytics.png` | Analytics page — health gauge + endpoint table |
| `swagger.png` | Swagger UI at `/docs` |
| `docker-compose.png` | `docker compose ps` output |

---

## 11. Release Notes Template

```markdown
## API Test Studio v1.0.0

### What's included
- Complete OpenAPI/Swagger test automation platform
- 8-phase pipeline: Parse → Generate → Execute → Validate → Persist → Analytics → Report
- FastAPI REST API with 19 endpoints and async job queue
- React dashboard with 5 pages, Plotly charts, MUI components
- Dockerized backend (532 MB) and frontend (55.6 MB)
- Docker Compose single-command platform startup
- GitHub Actions CI/CD with 4-job parallel pipeline

### Supported formats
- OpenAPI 3.x (JSON + YAML)
- Swagger 2.0 (JSON + YAML)

### System requirements
- Docker 24+ and Docker Compose v2 (recommended)
- OR Python 3.12+ and Node.js 22+ (local development)
```

---

## 12. Final Sign-Off

- [ ] All checklist items above are checked
- [ ] CI pipeline is green on the release branch
- [ ] At least one end-to-end run completed successfully
- [ ] Documentation is accurate and complete
- [ ] No sensitive data in the repository

**Release approved by:** _________________ **Date:** _________________
