import pytest
import json

from biodm import exceptions as exc
from biodm.utils.utils import json_bytes


def test_create_project(client):
    """"""
    # TODO: setup versioned A, B or C
    project = {'name': 'pr_test'}
    dataset = {'name': 'ds_test', 'contact': {'username': 'test'}}
    response = client.post('/bs', content=json_bytes(item))

    assert response.status_code == 201
    assert "id" in response.text
    assert "test" in response.text
