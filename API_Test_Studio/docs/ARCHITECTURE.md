# Architecture — API Test Studio

This document describes the internal structure, component responsibilities, and all major data flows of the API Test Studio platform.

---

## Table of Contents

- [High-Level Overview](#high-level-overview)
- [Component Diagram](#component-diagram)
- [Module Responsibilities](#module-responsibilities)
- [Execution Pipeline (Phases 2–8)](#execution-pipeline-phases-28)
- [Request Flow (Async Job)](#request-flow-async-job)
- [Analytics Flow](#analytics-flow)
- [Reporting Flow](#reporting-flow)
- [Data Model Relationships](#data-model-relationships)
- [Docker Architecture](#docker-architecture)
- [Design Principles](#design-principles)

---

## High-Level Overview

API Test Studio follows a **layered pipeline architecture**. Each phase is a self-contained module that reads from the phase before it and writes to the phase after it. No phase bypasses another.

```
Specification File
        │
        ▼
  ┌──────────┐
  │ Parser   │  api_parser/         — OpenAPI 3.x + Swagger 2.0 → ApiSpec
  └────┬─────┘
       │ ApiSpec
       ▼
  ┌────────────┐
  │ Generator  │  testcase_generator/ — ApiSpec → List[TestCase]
  └─────┬──────┘
        │ List[TestCase]
        ▼
  ┌──────────┐
  │ Executor │  executor/           — TestCase → ExecutionResult (live HTTP)
  └────┬─────┘
       │ List[ExecutionResult]
       ▼
  ┌────────────┐
  │ Validators │  validators/        — ExecutionResult → ValidationResult
  └─────┬──────┘
        │ List[ValidationResult]
        ▼
  ┌──────────┐
  │ Database │  database/           — All results persisted to SQLite
  └────┬─────┘
       │ run_id
       ▼
  ┌──────────────┐
  │  Analytics   │  analytics/      — DatabaseManager → AnalyticsSummary
  └──────┬───────┘
         │ AnalyticsSummary
         ▼
  ┌──────────┐
  │ Reporting│  reporting/          — Reports: HTML · PDF · CSV · JSON
  └──────────┘
```

---

## Component Diagram

```mermaid
graph LR
    subgraph Frontend ["Frontend (nginx:1.27-alpine · port 80)"]
        UI["React Dashboard\nTypeScript · MUI · Plotly"]
    end

    subgraph Backend ["Backend (python:3.12-slim · port 8000)"]
        API["FastAPI\n19 endpoints"]
        Jobs["Job Queue\nThreadPoolExecutor"]
        Settings["Settings\nSingleton"]

        subgraph Core ["Core Pipeline"]
            P2["api_parser\nOpenAPI · Swagger"]
            P3["testcase_generator\nPositive·Neg·Bound·Sec"]
            P4["executor\nHTTP · Auth · Retry"]
            P5["validators\n7 validators"]
            P6["database\nSQLite WAL"]
            P7["analytics\n7 analyzers"]
            P8["reporting\nHTML·PDF·CSV·JSON"]
        end
    end

    UI -->|"/api/* proxy"| API
    API --> Jobs
    Jobs -->|runs phases| P2
    P2 --> P3 --> P4 --> P5 --> P6 --> P7 --> P8
    API <-->|"read results"| P6
    API <-->|"read analytics"| P7
    API <-->|"serve reports"| P8
    API --> Settings
```

---

## Module Responsibilities

### Infrastructure Modules

| Module | Responsibility |
|---|---|
| `configs/` | Single source of truth for all configuration. `Config` loads `config.yaml` and `environments.yaml`. No hardcoded values exist anywhere else. |
| `constants/` | All named constants: `HttpMethod`, `HttpStatus`, `SpecFormat`, `ValidationType`, `AppMeta`, `FilePaths`. No magic strings outside this module. |
| `models/` | Pure immutable dataclasses: `ApiSpec`, `Endpoint`, `Parameter`, `TestCase`, `Assertion`, `ExecutionResult`, `AssertionResult`. No business logic. |
| `interfaces/` | Abstract base classes that enforce contracts: `ISpecParser`, `IValidator`, `ITestCaseGenerator`. All implementations must satisfy these. |
| `exceptions/` | Typed exception hierarchy per layer: `ConfigurationError`, `ParserError`, `ExecutionError`, `ValidationError`. |
| `utilities/` | Shared helpers: `LoggerFactory` (ANSI colour + rotating file), file I/O, UUID/timestamp/slug generators. |

### Phase Modules

| Phase | Module | Input | Output |
|---|---|---|---|
| 2 | `api_parser/` | Spec file path | `ApiSpec` |
| 3 | `testcase_generator/` | `ApiSpec` + `EnvironmentConfig` | `List[TestCase]` |
| 4 | `executor/` | `List[TestCase]` + `EnvironmentConfig` | `List[ExecutionResult]` |
| 5 | `validators/` | `List[TestCase]` + `List[ExecutionResult]` | `List[ValidationResult]` |
| 6 | `database/` | All Phase 2–5 outputs + `Config` | `run_id` (str) |
| 7 | `analytics/` | `DatabaseManager` + `run_id` | `AnalyticsSummary` |
| 8 | `reporting/` | `DatabaseManager` + `AnalyticsManager` + `run_id` | Report files |

---

## Execution Pipeline (Phases 2–8)

```mermaid
flowchart TD
    A[/"Spec File\n.yaml / .json"/] --> B

    subgraph P2 ["Phase 2 — Parser"]
        B["ParserManager\nfactory selects parser"]
        B1["openapi_parser\nOpenAPI 3.x"]
        B2["swagger_parser\nSwagger 2.0"]
        B --> B1 & B2
        B1 & B2 --> B3[/"ApiSpec\nendpoints · params · schemas"/]
    end

    B3 --> C

    subgraph P3 ["Phase 3 — Generator"]
        C["GeneratorManager"]
        C1["positive_generator"] & C2["negative_generator"]
        C3["boundary_generator"] & C4["security_generator"]
        C --> C1 & C2 & C3 & C4
        C1 & C2 & C3 & C4 --> C5["Deduplication\nengine"]
        C5 --> C6[/"List[TestCase]\n100s of cases"/]
    end

    C6 --> D

    subgraph P4 ["Phase 4 — Executor"]
        D["ExecutionManager\ncontext manager"]
        D1["url_builder"] --> D2["payload_builder"]
        D2 --> D3["authentication_manager"]
        D3 --> D4["request_manager\nrequests.Session"]
        D4 --> D5["retry_handler\nexp back-off"]
        D5 --> D6["response_wrapper\n→ ExecutionResult"]
        D --> D1
    end

    D6 --> E

    subgraph P5 ["Phase 5 — Validators"]
        E["ValidationManager\n3-level pipeline"]
        E1["StatusCode"] & E2["Header"] & E3["ResponseTime"]
        E4["JSON structure"] & E5["JSON Schema"]
        E6["Exact match"] & E7["Business rules"]
        E --> E1 & E2 & E3 & E4 & E5 & E6 & E7
    end

    E --> F

    subgraph P6 ["Phase 6 — Database"]
        F["DatabaseManager\npublic façade"]
        F1["execution_runs"] & F2["test_case_results"]
        F3["validation_details"] & F4["environments"]
        F --> F1 & F2 & F3 & F4
    end

    F --> G

    subgraph P7 ["Phase 7 — Analytics"]
        G["AnalyticsManager"]
        G1["HealthAnalyzer\n0-100 score"] & G2["TrendAnalyzer"]
        G3["EndpointAnalyzer"] & G4["ResponseTimeAnalyzer"]
        G5["FailureAnalyzer"] & G6["RegressionAnalyzer"]
        G --> G1 & G2 & G3 & G4 & G5 & G6
        G1 & G2 & G3 & G4 & G5 & G6 --> G7[/"AnalyticsSummary"/]
    end

    G7 --> H

    subgraph P8 ["Phase 8 — Reporting"]
        H["ReportManager"]
        H1["html_generator\nInteractive HTML"] & H2["pdf_generator\nReportLab PDF"]
        H3["csv_generator\n2× CSV"] & H4["json_generator\nStructured JSON"]
        H --> H1 & H2 & H3 & H4
    end
```

---

## Request Flow (Async Job)

The async job queue (Phase 9.3) decouples HTTP request handling from the long-running pipeline.

```mermaid
sequenceDiagram
    actor User
    participant Browser
    participant Nginx
    participant FastAPI
    participant JobStore
    participant Worker as ThreadPoolExecutor Worker
    participant DB as SQLite

    User->>Browser: uploads spec, clicks Execute
    Browser->>Nginx: POST /api/specifications/upload
    Nginx->>FastAPI: forward
    FastAPI-->>Browser: {filename, format} 201

    Browser->>Nginx: POST /api/jobs
    Nginx->>FastAPI: {filename, environment, options}
    FastAPI->>JobStore: create_job() → job_id
    FastAPI->>Worker: submit run_pipeline_job(job_id, ...)
    FastAPI-->>Browser: {job_id, poll_url} 202 Accepted

    loop Every 2.5 seconds
        Browser->>Nginx: GET /api/jobs/{job_id}
        Nginx->>FastAPI: forward
        FastAPI->>JobStore: get_job(job_id)
        FastAPI-->>Browser: {status, step, percent}
    end

    Worker->>Worker: Phase 2 parse
    Worker->>JobStore: set_progress("Parsing", 10%)
    Worker->>Worker: Phase 3 generate
    Worker->>JobStore: set_progress("Generating", 20%)
    Worker->>Worker: Phase 4 execute
    Worker->>JobStore: set_progress("Executing", 35%)
    Worker->>Worker: Phase 5 validate
    Worker->>JobStore: set_progress("Validating", 60%)
    Worker->>DB: Phase 6 persist → run_id
    Worker->>JobStore: set_progress("Persisting", 75%)
    Worker->>Worker: Phase 7 analytics
    Worker->>Worker: Phase 8 reports
    Worker->>JobStore: complete(run_id)

    Browser->>Nginx: GET /api/runs/{run_id}
    Nginx->>FastAPI: forward
    FastAPI->>DB: fetch run + validation summary
    FastAPI-->>Browser: RunDetailResponse
```

---

## Analytics Flow

```mermaid
graph LR
    DB[(SQLite\nDatabase)]
    DM["DatabaseManager\nread-only access"]
    AM["AnalyticsManager\norchestrator"]

    subgraph Analyzers
        H["HealthAnalyzer\npass_rate·rt·stability·availability"]
        T["TrendAnalyzer\ndaily/weekly/monthly buckets"]
        EP["EndpointAnalyzer\nmost/least/fastest/slowest"]
        RT["ResponseTimeAnalyzer\nmean·median·p95·p99·SLA"]
        FA["FailureAnalyzer\ncategory distribution · top-10"]
        RA["RegressionAnalyzer\nnew·fixed·unchanged failures"]
    end

    Stats["statistics.py\nmath primitives\nmean·median·std·percentile\nmoving_avg·slope"]

    DB --> DM --> AM
    AM --> H & T & EP & RT & FA & RA
    Stats -.->|"shared by all"| H & T & EP & RT & FA & RA
    H & T & EP & RT & FA & RA --> AS[/"AnalyticsSummary"/]
    AS --> API["FastAPI\n/api/analytics/{run_id}"]
    AS --> R["ReportManager\nembedded in reports"]
```

---

## Reporting Flow

```mermaid
graph TD
    DB[(SQLite)] --> DM["DatabaseManager"]
    DM --> AM["AnalyticsManager"]
    DM --> RM["ReportManager"]
    AM --> RM

    RM --> CG["chart_generator\nPlotly figures"]
    RM --> TL["template_loader\nJinja2 env"]

    CG --> HG["html_generator\n4.8 MB interactive HTML"]
    TL --> HG

    CG --> PG["pdf_generator\n~5 KB PDF"]
    TL --> PG

    DM --> CSV["csv_generator\n2× UTF-8 BOM CSV"]
    DM --> JSON["json_generator\n~244 KB JSON"]

    HG & PG & CSV & JSON --> OUT[/"reports/\nExecution_Report.*\nComparison_Report.*"/]
```

---

## Data Model Relationships

```mermaid
erDiagram
    execution_runs {
        text run_id PK
        text api_name
        text api_version
        text environment
        text execution_timestamp
        int total_test_cases
        int total_executed
        int passed
        int failed
        int errors
        real pass_percentage
        real avg_response_time_ms
        real health_score
        text health_rating
        text specification_file
    }

    test_case_results {
        text result_id PK
        text run_id FK
        text test_id
        text operation_id
        text endpoint
        text http_method
        text category
        text request_url
        int response_status_code
        real response_time_ms
        text validation_status
        text failure_reason
    }

    validation_details {
        text validation_detail_id PK
        text result_id FK
        text validator_name
        text status
        text message
        text severity
        real execution_time_ms
    }

    environments {
        text environment_id PK
        text name
        text base_url
        text auth_type
    }

    schema_version {
        int version PK
        text applied_at
    }

    execution_runs ||--o{ test_case_results : "has"
    test_case_results ||--o{ validation_details : "has"
```

---

## Docker Architecture

```mermaid
graph TB
    subgraph Host
        Browser["Browser\n:80 → :80"]
        Client["API Client\n:8000 → :8000"]
    end

    subgraph Compose ["Docker Compose (ats-network bridge)"]
        subgraph FE ["ats-frontend\nnginx:1.27-alpine · 55.6 MB"]
            Nginx["Nginx\nlisten :80\ntry_files → index.html\n/api/* → proxy_pass backend:8000"]
            Static["Static files\n/usr/share/nginx/html\nReact SPA (5 JS chunks)"]
        end

        subgraph BE ["ats-backend\npython:3.12-slim · 532 MB"]
            Uvicorn["Uvicorn\n0.0.0.0:8000"]
            App["FastAPI App\n19 endpoints"]
        end

        subgraph Volumes ["Named Volumes"]
            V1["ats-database"]
            V2["ats-uploaded-specs"]
            V3["ats-reports"]
            V4["ats-history"]
            V5["ats-logs"]
        end
    end

    Browser --> Nginx
    Nginx --> Static
    Nginx -->|"proxy_pass"| Uvicorn
    Client --> Uvicorn
    Uvicorn --> App
    App --- V1 & V2 & V3 & V4 & V5
```

---

## Design Principles

| Principle | Application |
|---|---|
| **Single Responsibility** | Every class does one thing. `RequestManager` sends requests. `RetryHandler` manages retries. `ResponseWrapper` converts responses. |
| **Open/Closed** | New parsers implement `ISpecParser` without touching existing code. New validators implement `IValidator`. |
| **Façade Pattern** | Every phase exposes a single manager class (`ParserManager`, `GeneratorManager`, etc.) hiding all internal complexity. |
| **Repository Pattern** | `ExecutionRepository`, `TestCaseRepository`, `ValidationRepository` hide all SQL. `DatabaseManager` is the only public interface. |
| **No Magic Strings** | Every literal is a named constant in `constants/`. |
| **No Hardcoded Config** | Every configurable value comes from `configs/config.yaml` or `configs/environments.yaml`. |
| **Dependency Inversion** | High-level modules (`executor`) depend on abstractions (`ISpecParser`), not concrete implementations. |
| **Layered Independence** | Each phase can be unit-tested in isolation. Phases 2–5 have no database dependency. |
