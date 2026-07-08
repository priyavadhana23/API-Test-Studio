# Developer Guide — API Test Studio

This guide explains the project structure, coding conventions, and how to extend the platform with new parsers, validators, analytics modules, and report formats.

---

## Table of Contents

- [Project Structure Quick Reference](#project-structure-quick-reference)
- [Coding Standards](#coding-standards)
- [Running Locally](#running-locally)
- [Adding a New Spec Parser](#adding-a-new-spec-parser)
- [Adding a New Validator](#adding-a-new-validator)
- [Adding a New Analytics Module](#adding-a-new-analytics-module)
- [Adding a New Report Format](#adding-a-new-report-format)
- [Adding a REST Endpoint](#adding-a-rest-endpoint)
- [Adding a Frontend Page](#adding-a-frontend-page)
- [Database Migrations](#database-migrations)
- [Testing Guidelines](#testing-guidelines)

---

## Project Structure Quick Reference

```
API_Test_Studio/
├── configs/              # All configuration — never hardcode values elsewhere
├── constants/            # All named constants — never use magic strings
├── models/               # Pure dataclasses — no business logic
├── interfaces/           # ABCs — contracts all implementations must satisfy
├── exceptions/           # Custom exception hierarchy
├── utilities/            # Shared helpers (logger, file I/O, etc.)
├── api_parser/           # Phase 2 — parsers implement ISpecParser
├── testcase_generator/   # Phase 3 — generators implement ITestCaseGenerator
├── executor/             # Phase 4 — HTTP execution engine
├── validators/           # Phase 5 — validators implement IValidator
├── database/             # Phase 6 — SQLite persistence (repository pattern)
├── analytics/            # Phase 7 — analyzers produce AnalyticsSummary
├── reporting/            # Phase 8 — generators produce report files
├── web_dashboard/backend/  # Phase 9 — FastAPI REST API
├── web_dashboard/frontend/ # Phase 10 — React TypeScript dashboard
└── .github/workflows/    # CI/CD pipeline
```

---

## Coding Standards

These conventions are enforced across every module:

### Python

| Rule | Detail |
|---|---|
| Type hints everywhere | All function signatures, dataclass fields, and class attributes must be typed |
| Docstrings | Every public class and function must have a docstring |
| No `print()` | All output goes through `get_logger(__name__)` |
| No magic strings | All literals must be defined in `constants/` |
| No hardcoded config | All values come from `Config` or `EnvironmentConfig` |
| One class per file | Except small related helpers |
| Public façade per phase | Each phase exposes one `*Manager` class only |
| Repository pattern | All SQL in repository classes; never in business logic |
| Fail fast with typed exceptions | Raise `ParserError`, `ExecutionError`, etc. — never bare `Exception` |

### TypeScript / React

| Rule | Detail |
|---|---|
| Strict TypeScript | `"strict": true` in `tsconfig.json` — no `any` |
| No direct Axios calls | Always use service layer (`runsService`, `analyticsService`, etc.) |
| No logic in components | Fetching goes in hooks or services, not JSX |
| Loading / error / empty states | Every data-fetching component uses `<PageState>` |
| Modular components | Max ~150 lines per component; extract sub-components |

---

## Running Locally

```bash
# Backend
cd API_Test_Studio
source .venv/bin/activate
uvicorn web_dashboard.backend.main:app --reload --port 8000

# Frontend (new terminal)
cd web_dashboard/frontend
npm run dev            # dev server with hot reload
npm run typecheck      # 0 TypeScript errors required
npm run build          # production build verification
```

---

## Adding a New Spec Parser

API Test Studio uses the Strategy pattern for parsers. Adding support for a new format (e.g. Postman Collection, AsyncAPI) requires three steps.

### Step 1 — Create the parser class

```python
# api_parser/postman_parser.py
from api_parser.parser_utils import load_file, build_operation_id
from exceptions.parser_exceptions import ParserError
from interfaces.parser_interface import ISpecParser
from models.api_spec import ApiSpec
from utilities.logger import get_logger

logger = get_logger(__name__)

class PostmanParser(ISpecParser):
    """Parses a Postman Collection v2.1 into an ApiSpec."""

    def can_parse(self, raw: dict) -> bool:
        """Return True if this parser can handle the given raw document."""
        return "info" in raw and "_postman_id" in raw.get("info", {})

    def parse(self, file_path: str) -> ApiSpec:
        """Parse a Postman Collection file into an ApiSpec."""
        raw = load_file(file_path)
        if not self.can_parse(raw):
            raise ParserError(f"Not a Postman Collection: {file_path}")

        # ... build and return ApiSpec
        logger.info("Parsed Postman Collection: %s", file_path)
        return ApiSpec(...)
```

### Step 2 — Register in the factory

```python
# api_parser/parser_factory.py
from api_parser.postman_parser import PostmanParser

class ParserFactory:
    def __init__(self):
        self._parsers = [
            OpenApiParser(),
            SwaggerParser(),
            PostmanParser(),   # ← add here
        ]
```

### Step 3 — Add the format constant

```python
# constants/spec_formats.py
class SpecFormat(str, Enum):
    OPENAPI_3   = "openapi3"
    SWAGGER_2   = "swagger2"
    POSTMAN     = "postman"   # ← add here
```

That's it. `ParserManager.parse()` will automatically try the new parser.

---

## Adding a New Validator

Validators implement `IValidator` and are registered in `ValidationManager`.

### Step 1 — Create the validator

```python
# validators/content_length_validator.py
from interfaces.validator_interface import IValidator
from models.execution_result import ExecutionResult, AssertionResult
from models.test_case import TestCase
from utilities.logger import get_logger

logger = get_logger(__name__)

class ContentLengthValidator(IValidator):
    """Validates that the response Content-Length header is present."""

    def validate(self, test_case: TestCase, result: ExecutionResult) -> AssertionResult:
        header = (result.response_headers or {}).get("content-length")
        if header is not None:
            return AssertionResult(passed=True, message="Content-Length header present")
        return AssertionResult(
            passed=False,
            message="Content-Length header missing",
            severity="low",
        )
```

### Step 2 — Register in ValidationManager

```python
# validators/validation_manager.py
from validators.content_length_validator import ContentLengthValidator

class ValidationManager:
    def __init__(self):
        self._validators = [
            StatusCodeValidator(),
            HeaderValidator(),
            ResponseTimeValidator(),
            JsonValidator(),
            SchemaValidator(),
            ExactResponseValidator(),
            BusinessRuleValidator(),
            ContentLengthValidator(),   # ← add here
        ]
```

---

## Adding a New Analytics Module

Analytics modules are invoked by `AnalyticsManager` and contribute fields to `AnalyticsSummary`.

### Step 1 — Create the analyzer

```python
# analytics/latency_percentile_analyzer.py
from analytics.statistics import percentile
from database.database_manager import DatabaseManager

class LatencyPercentileAnalyzer:
    """Computes response time percentiles at custom thresholds."""

    def __init__(self, db: DatabaseManager):
        self._db = db

    def analyze(self, run_id: str) -> dict:
        results = self._db.get_test_results(run_id)
        rts = [r.response_time_ms for r in results if r.response_time_ms]
        return {
            "p50_ms": percentile(rts, 50),
            "p75_ms": percentile(rts, 75),
            "p95_ms": percentile(rts, 95),
            "p99_ms": percentile(rts, 99),
        }
```

### Step 2 — Add a field to AnalyticsSummary

```python
# analytics/models.py
@dataclass
class AnalyticsSummary:
    ...
    latency_percentiles: Optional[dict] = None   # ← add here
```

### Step 3 — Call from AnalyticsManager

```python
# analytics/analytics_manager.py
from analytics.latency_percentile_analyzer import LatencyPercentileAnalyzer

class AnalyticsManager:
    def run_analysis(self, run_id: str) -> AnalyticsSummary:
        ...
        summary.latency_percentiles = LatencyPercentileAnalyzer(self._db).analyze(run_id)
        return summary
```

---

## Adding a New Report Format

Report generators receive a `DatabaseManager` and `AnalyticsManager` and write a file to the output directory.

### Step 1 — Create the generator

```python
# reporting/xml_generator.py
import xml.etree.ElementTree as ET
from pathlib import Path
from database.database_manager import DatabaseManager
from utilities.logger import get_logger

logger = get_logger(__name__)

class XmlGenerator:
    """Generates an XML report for integration with legacy systems."""

    def __init__(self, db: DatabaseManager):
        self._db = db

    def generate(self, run_id: str, output_dir: Path) -> Path:
        run = self._db.get_run(run_id)
        root = ET.Element("TestReport", run_id=run_id)
        ET.SubElement(root, "ApiName").text = run.api_name
        ET.SubElement(root, "Passed").text = str(run.passed)
        # ... build full XML tree

        output_path = output_dir / f"Execution_Report.xml"
        ET.ElementTree(root).write(output_path, encoding="utf-8", xml_declaration=True)
        logger.info("XML report written: %s", output_path)
        return output_path
```

### Step 2 — Register in ReportManager

```python
# reporting/report_manager.py
from reporting.xml_generator import XmlGenerator

class ReportManager:
    def generate_report(self, run_id: str) -> list[Path]:
        paths = []
        paths.append(self._html.generate(run_id, self._output_dir))
        paths.append(self._pdf.generate(run_id, self._output_dir))
        paths.extend(self._csv.generate(run_id, self._output_dir))
        paths.append(self._json.generate(run_id, self._output_dir))
        paths.append(XmlGenerator(self._db).generate(run_id, self._output_dir))  # ← add
        return [p for p in paths if p and p.exists()]
```

---

## Adding a REST Endpoint

### Step 1 — Add a Pydantic schema

```python
# web_dashboard/backend/schemas/my_feature.py
from pydantic import BaseModel

class MyFeatureResponse(BaseModel):
    field_one: str
    field_two: int
```

### Step 2 — Create (or extend) a router

```python
# web_dashboard/backend/routers/my_feature.py
from fastapi import APIRouter, Depends
from web_dashboard.backend.config.settings import Settings, get_settings
from web_dashboard.backend.schemas.my_feature import MyFeatureResponse

router = APIRouter(tags=["My Feature"])

@router.get("/api/my-feature", response_model=MyFeatureResponse)
def get_my_feature(settings: Settings = Depends(get_settings)):
    return MyFeatureResponse(field_one="hello", field_two=42)
```

### Step 3 — Register in main.py

```python
# web_dashboard/backend/main.py
from web_dashboard.backend.routers import my_feature as my_feature_router
app.include_router(my_feature_router.router)
```

> **Important:** Register routers with more-specific literal paths before routers with wildcard `{param}` paths, or FastAPI will swallow them.

---

## Adding a Frontend Page

### Step 1 — Create the page component

```tsx
// src/pages/MyPage.tsx
import { Box, Typography } from '@mui/material';
import { useAsync } from '../hooks/useAsync';
import PageState from '../components/PageState';
import myService from '../services/myService';

export default function MyPage() {
  const { data, loading, error, refetch } = useAsync(
    () => myService.getData(),
    [],
  );

  if (loading || error || !data) {
    return <PageState loading={loading} error={error} onRetry={refetch} />;
  }

  return (
    <Box>
      <Typography variant="h5">My Page</Typography>
      {/* render data */}
    </Box>
  );
}
```

### Step 2 — Add the route

```tsx
// src/App.tsx
import MyPage from './pages/MyPage';

<Route path="/my-page" element={<MyPage />} />
```

### Step 3 — Add the nav item

```tsx
// src/layouts/MainLayout.tsx
const NAV_ITEMS = [
  ...
  { label: 'My Page', path: '/my-page', icon: <StarIcon /> },
];
```

### Step 4 — Add a service

```ts
// src/services/myService.ts
import apiClient from './apiClient';
import type { MyResponse } from '../types/api';

const myService = {
  getData: async (): Promise<MyResponse> => {
    const { data } = await apiClient.get<MyResponse>('/api/my-feature');
    return data;
  },
};

export default myService;
```

---

## Database Migrations

Schema changes must go through the migration runner to maintain upgrade compatibility.

### Step 1 — Increment the version

```python
# database/migrations.py
CURRENT_VERSION = 2   # was 1
```

### Step 2 — Add a migration function

```python
def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Add index on test_case_results.category for analytics performance."""
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tcr_category ON test_case_results(category)"
    )

MIGRATIONS = {
    2: _migrate_v1_to_v2,
}
```

The `MigrationRunner.run()` method applies all pending migrations in order automatically.

---

## Testing Guidelines

The project uses standard `pytest`. Tests are not included in the Phase 10 production build but the structure is ready for them.

```
tests/
├── unit/
│   ├── test_openapi_parser.py
│   ├── test_positive_generator.py
│   ├── test_status_code_validator.py
│   └── ...
├── integration/
│   ├── test_full_pipeline.py
│   └── test_database_manager.py
└── conftest.py
```

### Running tests

```bash
pytest tests/ -v
pytest tests/unit/ -v                    # unit only
pytest tests/integration/ -v            # integration only
pytest -k "test_parser" -v              # filter by name
pytest --tb=short -q                    # quiet mode
```

### Writing a unit test

```python
# tests/unit/test_openapi_parser.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from api_parser.openapi_parser import OpenApiParser

def test_parses_petstore():
    parser = OpenApiParser()
    spec = parser.parse("uploaded_specs/petstore_openapi3.yaml")
    assert spec.title == "Petstore"
    assert len(spec.endpoints) > 0
```
