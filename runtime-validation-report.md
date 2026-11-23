# Runtime Validation Report

**Generated**: 2026-11-23
**Target**: `compra-juegos`
**Scope**: Local test baseline and deployed EC2/OpenObserve validation

## Summary

| Step | Status | Exit code | Details |
|---|---|---:|---|
| Startup/readiness | PASS | 0 | Local Compose API and deployed `https://tienda-videojuegos.duckdns.org/api/health` returned HTTP 200. |
| Backend/API tests | PASS | 0 | 20 pytest tests passed with FastAPI TestClient and in-memory SQLite. |
| Angular production build | PASS | 0 | `npm run build` succeeded; initial bundle is 619.46 kB, above the 500 kB warning budget. |
| Playwright user journeys in Docker | PASS | 0 | Five complete journeys passed in 26.24 seconds. |
| Playwright functional matrix in Docker | PASS | 0 | 1,700 cases passed in 478.43 seconds with four workers. |
| Production API | PASS | 0 | Deployed `/api/health` and `/api/games` returned HTTP 200. |
| OpenTelemetry ingestion | PASS | 0 | OpenObserve accepted Collector posts for metrics, logs, and traces with HTTP 200; Collector was running with zero restarts. |
| Resource dashboard | PASS | 0 | `Operación CompraJuegos` is saved and shows CPU, RAM, and network metrics. |
| Operational alert | NEEDS_SIGNOFF | n/a | OpenObserve requires a configured notification destination or workflow; this stack has no SMTP destination. |
| Temperature | UNAVAILABLE | n/a | EC2 exposes no thermal sensors; real °C cannot be reported by this instance. |

**Overall**: NEEDS_SIGNOFF — local tests, production telemetry, and dashboard are verified; alert delivery requires a real notification destination, and EC2 cannot provide temperature sensors.

## Environment

- Node.js: available, `v22.22.0`.
- Python: available, `3.10.11`.
- Playwright: available, `1.65.2`; Chromium ran the browser suite.
- Docker CLI and daemon: available, Docker `29.9.3`.
- The last successful GitHub Actions deployment was run `45123193517`; its CI/CD test and deployment events were accepted by OpenObserve with HTTP 200.
- Production domains: `tienda-videojuegos.duckdns.org` and `obs-videojuegos.duckdns.org`.
- EC2 has 908 MiB RAM, no swap, and approximately 333 MiB free on its 6.7 GiB root volume at the last check.
- E2E Docker infrastructure uses its isolated SQLite volume and test-only admin credentials. No production credentials were used for this validation.

## Backend/API Coverage

Command (from `backend/`): `python -m pytest -q`

Result: **20 passed**, exit code `0`.

The suite covers all 15 HTTP operations:

| Method | Endpoint | Covered behaviors |
|---|---|---|
| GET | `/api/health` | Healthy response |
| POST | `/api/auth/register` | Registration, duplicate email, password and field boundaries |
| POST | `/api/auth/login` | Valid/invalid credentials and inactive account rejection |
| GET | `/api/auth/me` | Valid, missing, invalid, and deactivated-user token |
| GET | `/api/users` | Admin authorization, customer denial, result limit |
| POST | `/api/users` | Admin creation, duplicate email, forbidden roles, field boundaries |
| PATCH | `/api/users/{user_id}` | Update, password validation, reactivation, not found, last-admin protection |
| DELETE | `/api/users/{user_id}` | Logical deactivation, idempotency, not found, last-admin protection |
| GET | `/api/games` | List, category filter, search |
| GET | `/api/games/{game_id}` | Existing and missing game |
| POST | `/api/games` | Admin creation, role protection, field validation and limits |
| PATCH | `/api/games/{game_id}` | Update, invalid values, not found |
| DELETE | `/api/games/{game_id}` | Delete, role protection, not found, sold-game protection |
| POST | `/api/purchases` | Authentication, payload validation, missing game, insufficient stock, successful checkout |
| GET | `/api/purchases` | Authentication and persisted purchase history |

## Docker and Browser Coverage

The exact E2E Docker setup used by GitHub Actions was built and started with:

```powershell
docker compose -f compose.e2e.yaml up --build -d
```

Both API and web containers started; the API health check became healthy and `http://127.0.0.1:8080/api/health` returned HTTP 200.

Commands (from `e2e/`):

```powershell
python -m pytest -q --tb=short test_store.py
python -m pytest -q -n 4 --tb=short test_ui_matrix.py
```

Result: **1,705 passed total**, exit code `0` across both commands. The temporary E2E containers were stopped after validation.

| Suite | Cases | Coverage |
|---|---:|---|
| `test_store.py` | 5 | Invalid login; header/footer navigation; cart quantity/removal and anonymous checkout guard; customer registration, purchase and history; admin user/game CRUD, soft deletion and reactivation |
| `test_ui_matrix.py` | 100 | Header/footer buttons and destination routes across five viewports and anonymous/admin states |
| `test_ui_matrix.py` | 480 | Cart entry buttons, add/remove/increment/decrement sequences, item counts and totals |
| `test_ui_matrix.py` | 320 | Login/registration entry points, email/password/name boundaries, password visibility toggle and dialog transitions |
| `test_ui_matrix.py` | 350 | User create/edit form roles, email/name/password validation and limits |
| `test_ui_matrix.py` | 430 | Game create/edit form boundaries, number constraints, URL validation and cancel flow |
| `test_ui_matrix.py` | 20 | Representative catalog search/category filters and no-results state |

Browser request observations include UTC timestamp, endpoint, HTTP method, status code, and response time; they are attached to JUnit properties for the end-to-end journeys.

The purchase flow persists test data in its isolated E2E SQLite volume. Do not point it at a production database.

## Additional Validation

- `npm run build`: exit code `0`; Angular build succeeded.
- Build warning: initial bundle size is 619.46 kB, exceeding the configured 500 kB warning budget by 119.46 kB, below the 1 MB error budget.
- Production and E2E Compose definitions pass `docker compose config --quiet`.
- Non-blocking warnings: Starlette's `TestClient` warns about its current `httpx` integration; pytest-playwright warns about a deprecated fixture pattern in its `base_url` fixture.
- GitHub Actions runs the five user journeys, then the 1,700-case matrix with four workers and a 15-minute timeout. Workflow YAML parses successfully.

## Runtime Verdict

```yaml
environment:
  docker: AVAILABLE — Docker 29.9.3; E2E containers healthy
  node: AVAILABLE — v22.22.0
  playwright: AVAILABLE — Playwright 1.65.2 with Chromium
  infra-tier: PRIMARY(Docker-based) — Compose E2E stack built and tested
  browser-tier: PRIMARY(Playwright) — 1,705 tests passed
startup: PASS — local API and deployed `/api/health` returned HTTP 200
integration: PASS — exit_code: 0, passed: 20, failed: 0, skipped: 0; all 15 API operations
e2e: PASS — exit_code: 0, passed: 1,705, failed: 0; browser journeys and functional matrix
telemetry: PASS — metrics, logs, and traces accepted by OpenObserve with HTTP 200; Collector restarts: 0
dashboard: PASS — Operación CompraJuegos saved; CPU, RAM, and network data visible
alert: NEEDS_SIGNOFF — no SMTP or webhook destination is configured
temperature: UNAVAILABLE — EC2 exposes no thermal sensor
overall: NEEDS_SIGNOFF — alert delivery requires a real destination; temperature is unavailable on this EC2
```

## Remaining gaps

- Configure a real webhook destination or SMTP before creating the scheduled CPU alert. Never commit notification URLs, tokens, or credentials.
- Temperature in °C cannot be validated on this EC2 because the host does not expose a thermal sensor; use hardware that exposes sensors if this is mandatory.
- Monitor the EC2 disk and memory headroom before further deployments; do not remove legacy containers/images or data volumes without deciding whether rollback data is needed.
