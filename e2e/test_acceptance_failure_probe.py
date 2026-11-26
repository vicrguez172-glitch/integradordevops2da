import os

import pytest
from playwright.sync_api import Page, expect


def test_acceptance_failure_probe(page: Page, app_url: str):
    if os.getenv("RUN_ACCEPTANCE_FAILURE_PROBE") != "1":
        pytest.skip("Enable this only through the manual deployment-gate probe.")

    page.goto(app_url)
    expect(
        page.get_by_role("heading", name="INTENTIONAL ACCEPTANCE FAILURE PROBE")
    ).to_be_visible()
