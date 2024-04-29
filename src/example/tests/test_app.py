import sys
from pathlib import Path

import pytest
from starlette.responses import HTMLResponse
from starlette.testclient import TestClient

from example import app


# @pytest.fixture
# def test_client_factory() -> TestClient:
#     return TestClient

def test_liveness():
    with TestClient(app.main(), backend_options={"use_uvloop": True}) as client:
        response = client.get('/live')
        assert response.status_code == 200
        assert response.text == 'live\n'
