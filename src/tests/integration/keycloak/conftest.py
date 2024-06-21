import os
import pytest

@pytest.fixture(scope="session", autouse=True)
def srv_endpoint():
    key = 'API_ENDPOINT'

    if key in os.environ:
        return os.environ[key]
 
    return "http://10.10.0.6:8000"
