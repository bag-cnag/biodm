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


def test_release_version(client):
    """"""
    item = {"name": "ver_test"}
    response = client.post('/bs', content=json_bytes(item))

    assert response.status_code == 201

    update = {"name": "ver_updated"}
    response = client.post('/bs/1_1/release', content=json_bytes(update))

    assert response.status_code == 200
    json_response = json.loads(response.text)

    assert json_response['id'] == 1
    assert json_response['version'] == 2
    assert json_response['name'] == update['name']

    response = client.get('/bs?id=1')

    assert response.status_code == 200
    json_response = json.loads(response.text)
    
    assert len(json_response) == 2 
    assert json_response[0]['version'] == 1
    assert json_response[0]['name'] == item['name']
    assert json_response[1]['version'] == 2
    assert json_response[1]['name'] == update['name']


@pytest.mark.xfail(raises=exc.UpdateVersionedError)
def test_no_update_version_resource_through_write(client):
    item = {'name': '1234'}

    response = client.post('/bs', content=json_bytes(item))
    assert response.status_code == 201

    update = {'id': '1', 'version': '1', 'name': '4321'}
    response = client.post('/bs', content=json_bytes(update))
    assert response.status_code == 409

# TODO: test this on nested.
