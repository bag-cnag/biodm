import pytest

@pytest.fixture(scope="session", autouse=True)
def srv_endpoint():
    return "http://10.10.0.6:8000/"
