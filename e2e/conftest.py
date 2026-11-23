from collections import defaultdict, deque
import json
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page


@pytest.fixture
def api_request_metrics(page: Page, request):
    started: dict[tuple[str, str], deque[float]] = defaultdict(deque)
    observations: list[dict[str, object]] = []

    def on_request(browser_request):
        if "/api/" in browser_request.url:
            started[(browser_request.url, browser_request.method)].append(time.perf_counter())

    def on_response(response):
        browser_request = response.request
        key = (browser_request.url, browser_request.method)
        if not started[key]:
            return
        elapsed = (time.perf_counter() - started[key].popleft()) * 1000
        observations.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "endpoint": urlsplit(browser_request.url).path,
                "method": browser_request.method,
                "status_code": response.status,
                "response_time_ms": round(elapsed, 2),
            }
        )

    def on_failed(browser_request):
        key = (browser_request.url, browser_request.method)
        if not started[key]:
            return
        start = started[key].popleft()
        observations.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "endpoint": urlsplit(browser_request.url).path,
                "method": browser_request.method,
                "status_code": None,
                "response_time_ms": round((time.perf_counter() - start) * 1000, 2),
                "error": browser_request.failure,
            }
        )

    page.on("request", on_request)
    page.on("response", on_response)
    page.on("requestfailed", on_failed)
    yield observations
    request.node.user_properties.append(("http_request_metrics", json.dumps(observations)))
    print("HTTP_REQUEST_METRICS=" + json.dumps(observations, ensure_ascii=False))


@pytest.fixture(scope="session")
def app_url() -> str:
    return os.getenv("E2E_BASE_URL", "http://127.0.0.1:8080").rstrip("/")


@pytest.fixture
def admin_credentials() -> tuple[str, str]:
    return (
        os.getenv("E2E_ADMIN_EMAIL", "admin@example.com"),
        os.getenv("E2E_ADMIN_PASSWORD", "local-admin-change-this"),
    )
