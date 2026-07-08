# User Guide — API Test Studio

This guide walks through the complete workflow from uploading a specification to downloading reports.

---

## Prerequisites

The platform must be running. See [INSTALLATION.md](INSTALLATION.md) for setup.

- Dashboard: [http://localhost](http://localhost) (Docker Compose) or [http://localhost:5173](http://localhost:5173) (local dev)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Navigation

The sidebar contains four pages:

| Page | Purpose |
|---|---|
| **Dashboard** | Summary cards and recent run table |
| **Upload** | Upload a spec and execute the pipeline |
| **Runs** | Full execution history with search and filter |
| **Analytics** | Deep analytics for any run |

---

## Step 1 — Upload a Specification

Navigate to **Upload** in the sidebar.

### Supported formats

| Format | Extensions |
|---|---|
| OpenAPI 3.x | `.yaml`, `.yml`, `.json` |
| Swagger 2.0 | `.yaml`, `.yml`, `.json` |

### How to upload

1. Drag and drop a spec file onto the drop zone, or click **Browse**.
2. The platform validates the file type and size (max 16 MB) before accepting it.
3. Once accepted, a **Ready** chip appears with the filename and size.

### Sample specs

Three sample specifications are included in `uploaded_specs/`:

| File | Description |
|---|---|
| `httpbin_verification.yaml` | 8-endpoint HTTPBin API (OpenAPI 3.x) |
| `petstore_openapi3.yaml` | Classic Pet Store (OpenAPI 3.x) |
| `bookstore_swagger2.json` | Bookstore CRUD API (Swagger 2.0) |

---

## Step 2 — Configure Execution

### Environment selection

Choose the target environment from the dropdown:

| Environment | Purpose |
|---|---|
| `Development` | Local or dev server testing |
| `Staging` | Pre-production verification |
| `Production` | Live API health checks |

Base URLs for each environment are configured in `configs/environments.yaml`.

### Base URL override

Enter a URL in the **Base URL Override** field to test against a different server without editing the config file. Example: `https://httpbin.org`.

### Execution options

| Option | Default | Description |
|---|---|---|
| Generate Reports | On | Produces HTML, PDF, CSV, and JSON reports after execution |
| Verify SSL Certificates | On | Validate TLS certificate chain |
| Timeout (seconds) | 30 | Per-request HTTP timeout (1–300 s) |

---

## Step 3 — Execute the Pipeline

Click **Execute Pipeline**. The button is disabled until a file is selected.

### Progress screen

The progress screen shows:
- A stage stepper with 10 named steps
- A progress percentage chip
- The current step label
- The job start time

| Step | Phase |
|---|---|
| Uploading | File transfer |
| Loading configuration | Phase 1 bootstrap |
| Parsing API specification | Phase 2 |
| Generating test cases | Phase 3 |
| Executing HTTP requests | Phase 4 |
| Validating responses | Phase 5 |
| Persisting results | Phase 6 |
| Running analytics | Phase 7 |
| Generating reports | Phase 8 |
| Done | Complete |

Execution typically takes 30–120 seconds depending on the number of endpoints and API response times.

### If execution fails

An error screen appears with the failure reason and a **Try Again** button. Common causes:

- The API is unreachable (check base URL and network)
- SSL certificate invalid (disable "Verify SSL" for self-signed certs)
- Invalid spec file (check the spec manually with a linter)

---

## Step 4 — View Run Details

After execution completes, click **View Run**. The Run Details page shows:

### Execution Summary

Six stat cards: Total Tests, Passed, Failed, Errors, Skipped, Endpoints.

A pass-rate progress bar coloured green (≥80%), amber (50–79%), or red (<50%).

### Execution Details table

| Field | Description |
|---|---|
| Run ID | Unique identifier (truncated for display) |
| API Name | Parsed from the spec title |
| Environment | Selected at execution time |
| Date | ISO-8601 execution timestamp |
| Total Time | Wall-clock seconds |
| Avg Response | Mean HTTP response time |
| Spec File | Original filename |

### Analytics Highlights

A quick-view table showing the most important analytics values:
- Health Score and Rating
- Mean, Median, P95, P99 response times
- SLA compliance percentage
- Most failed and fastest/slowest endpoints

### Charts

| Chart | Description |
|---|---|
| Pass vs Fail pie | Proportion of passed/failed/skipped/error results |
| Health Score gauge | Colour-coded 0–100 gauge with thresholds |
| Failure Distribution | Top failure categories as a bar chart |
| Endpoint Pass Rate | Horizontal bar chart sorted by pass rate |

### Validator Breakdown

A table showing how each of the 7 validators performed:

| Validator | What it checks |
|---|---|
| StatusCodeValidator | HTTP status code matches expected |
| HeaderValidator | Content-Type and custom headers |
| ResponseTimeValidator | Response time ≤ threshold |
| JsonValidator | Body is valid JSON, dot-notation field extraction |
| JsonSchemaValidator | Body matches JSON Schema definition |
| ExactResponseValidator | Exact field values, template matching |
| BusinessRuleValidator | Custom domain rules |

### Recommendations

Actionable improvement suggestions generated by the Health Analyzer based on the run's scores.

---

## Step 5 — Explore Analytics

Navigate to **Analytics** in the sidebar, or click **View Analytics** from the completion screen.

### Run selector

Use the dropdown at the top to switch between any historical run.

### Health Score breakdown

The gauge chart shows the composite 0–100 score, plus the four component scores:
- Pass Rate Score
- Response Time Score
- Stability Score
- Availability Score

### Response Time Statistics

A grid of 10 metrics: sample count, mean, median, std dev, min, max, P95, P99, SLA threshold, and SLA compliance percentage.

### Endpoint Performance

An interactive bar chart and detailed table showing pass rate, execution count, and response time percentiles per endpoint.

### Failure Distribution

A bar chart of failure categories (schema validation, status code, timeout, auth, etc.) with counts and percentages.

### Trend Analysis

A line chart showing how the selected metric (pass rate, response time) has changed over time, with a moving average overlay.

### Regression Summary

When multiple runs exist, the regression panel shows:
- New failures (appeared in this run vs baseline)
- Fixed failures (resolved since baseline)
- Unchanged failures
- Pass rate delta
- Average response time delta

---

## Step 6 — Browse Runs

Navigate to **Runs** in the sidebar.

### Search and filter

| Control | Description |
|---|---|
| Search box | Filter by API name, run ID, or environment |
| Status filter | Pass ≥ 80% / Pass < 80% / All |

### Table columns

Run ID · API Name · Environment · Date · Tests · Pass % · Health · Avg RT (ms)

Click any row to go to the Run Details page.

---

## Step 7 — Download Reports

From the Run Details page, reports are available after the pipeline completes.

> *(Phase 9.7 — report download from the dashboard — is planned for a future sprint.)*  
> In the current version, reports can be downloaded via the REST API:

```bash
# List reports for a run
curl http://localhost:8000/api/reports/{run_id}

# Download HTML report
curl -O http://localhost:8000/api/reports/{run_id}/download/Execution_Report.html

# Download PDF
curl -O http://localhost:8000/api/reports/{run_id}/download/Execution_Report.pdf
```

Reports are also written directly to `reports/` on the backend filesystem (or the `ats-reports` Docker volume).

### Report formats

| File | Size (typical) | Use case |
|---|---|---|
| `Execution_Report.html` | 4–5 MB | Interactive dashboard, share with team |
| `Execution_Report.pdf` | 5–10 KB | Executive summary, email attachment |
| `Execution_Report_results.csv` | 10–100 KB | Import into Excel, BI tools |
| `Execution_Report_validation.csv` | 20–200 KB | Detailed per-assertion analysis |
| `Execution_Report.json` | 50–300 KB | Downstream tooling, custom dashboards |

---

## Dashboard Page

The Dashboard shows an at-a-glance summary of the most recent 50 runs:

| Card | Value |
|---|---|
| Total Runs | Count of all runs in history |
| Avg Pass Rate | Mean pass percentage across recent runs |
| Avg Response Time | Mean HTTP response time across recent runs |
| Avg Health Score | Mean health score (0–100) |

The **Recent Runs** table shows the last 10 runs. Click any row to go to the Run Details page.
