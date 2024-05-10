import json

from starlette.testclient import TestClient

from .conftest import json_bytes


def test_resource_schema(client_args):
    """"""
    with TestClient(**client_args) as client:
        response = client.get('/as/schema/')
        assert response.status_code == 200
        json_response = json.loads(response.text)
        assert "/" in json_response['paths']
        assert "/search/" in json_response['paths']


def test_create_unary_resource(client_args):
    """"""
    with TestClient(**client_args) as client:
        response = client.post('/bs/', content=json_bytes({'name': 'test'}))
        assert response.status_code == 201
        assert "id" in response.text
        assert "test" in response.text
