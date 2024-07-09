import pytest
import json

from biodm import exceptions as exc
from biodm.utils.utils import json_bytes


def test_create_versioned_resource(client):
    """"""
    item = {"name": "ver_test"}
    response = client.post('/bs', content=json_bytes(item))

    assert response.status_code == 201

    json_response = json.loads(response.text)

    assert json_response['id'] == 1
    assert json_response['version'] == 1
