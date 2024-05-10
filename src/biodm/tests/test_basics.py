from starlette.testclient import TestClient
from .app import client_args#, json_bytes

def test_live_endpoint(client_args):
    """"""
    with TestClient(**client_args) as client:
        response = client.get('/live')
        assert response.status_code == 200
        assert response.text == 'live\n'

def test_api_schema(client_args):
    """"""
    with TestClient(**client_args) as client:
        response = client.get('/schema')
        assert response.status_code == 200
        assert "biodm_test" in response.text
        assert "0.1.0"      in response.text

# TODO:
# def test_login_endpoint():
# def test_users
# def test_groups
