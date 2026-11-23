# Pre-deployment Runtime Validation Report

**Generated**: 2026-11-22T21:19:43-06:00
**Target**: `compra-juegos`
**Scope**: Local API, production build, and Docker E2E validation before GitHub/EC2 publication

## Summary

| Step | Status | Exit code | Details |
|---|---|---:|---|
| Startup/readiness | PASS | 0 | Docker Compose E2E stack started; API `/api/health` returned HTTP 200 and `{"status":"ok"}`. |
| Backend/API tests | PASS | 0 | 20 pytest tests passed with FastAPI TestClient and in-memory SQLite. |
| Angular production build | PASS | 0 | `npm run build` succeeded; initial bundle is 619.46 kB, above the 500 kB warning budget. |
| Playwright user journeys in Docker | PASS | 0 | Five complete journeys passed in 26.24 seconds. |
| Playwright functional matrix in Docker | PASS | 0 | 1,700 cases passed in 478.43 seconds with four workers. |
| Docker production/OpenObserve | NOT RUN | n/a | Compose syntax validated, but the production stack was not started. |
| GitHub/EC2 publication | BLOCKED | n/a | The remote is empty; connected GitHub account has read-only permission. EC2/OpenObserve Actions secrets cannot be inspected due GitHub API HTTP 403. |

**Overall**: NEEDS_SIGNOFF — local backend, build, and Docker E2E validation passed. GitHub publication, production OpenObserve stack, and EC2 runtime remain unverified.

## Environment

- Node.js: available, `v22.22.0`.
- Python: available, `3.10.11`.
- Playwright: available, `1.65.2`; Chromium ran the browser suite.
- Docker CLI and daemon: available, Docker `29.9.3`.
- GitHub CLI: authenticated as `vic0192`; repository viewer permission is `READ`.
- Target repository: `https://github.com/vicrguez172-glitch/integradordevops2da`, public and empty (no default branch).
- Querying Actions secrets/variables returned HTTP 403 because the connected account lacks permission.
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
startup: PASS — Docker API health returned HTTP 200
integration: PASS — exit_code: 0, passed: 20, failed: 0, skipped: 0; all 15 API operations
e2e: PASS — exit_code: 0, passed: 1,705, failed: 0; browser journeys and functional matrix
overall: NEEDS_SIGNOFF — GitHub publication/EC2 blocked by missing repository write permission; production telemetry not tested
```

## Blockers / Next Steps

- Grant write access to the authenticated GitHub account or authenticate GitHub CLI as an account with repository write access. The current account sees only `READ`, so a push cannot be made.
- Configure and verify in GitHub Actions the `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY`, `EC2_KNOWN_HOSTS`, `OPENOBSERVE_URL`, `OPENOBSERVE_EMAIL`, and `OPENOBSERVE_PASSWORD` secrets. Never paste these values in chat or commit them.
- Set up any optional Actions variables (`OPENOBSERVE_ORG`, `OPENOBSERVE_STREAM`, `EC2_APP_DIR`) if needed.
- Start the production Compose stack with secure credentials only after checking `.env` values locally, then confirm logs, traces, endpoint metrics, host CPU/RAM/network data, and available temperature sensors in OpenObserve.
- Deploy to EC2 only after repository write access and required Actions secrets are available.
