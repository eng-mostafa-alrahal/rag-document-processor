from __future__ import annotations

import os

import httpx
import pytest


@pytest.mark.e2e
@pytest.mark.skipif(os.getenv("E2E_STACK") != "1", reason="Set E2E_STACK=1 and run docker-compose + API")
def test_health_endpoint_against_running_server() -> None:
    base = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8000")
    r = httpx.get(f"{base}/api/v1/health", timeout=5.0)
    r.raise_for_status()
    assert r.json().get("status") == "ok"
