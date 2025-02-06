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

    assert json_response['version'] == 1
    assert json_response['name'] == item['name']


def test_release_version(client):
    """"""
    item = {"name": "ver_test"}
    response = client.post('/bs', content=json_bytes(item))

    assert response.status_code == 201
    item_res = json.loads(response.text)

    update = {"name": "ver_updated"}
    response = client.post(f"/bs/{item_res['id']}_1/release", content=json_bytes(update))

    assert response.status_code == 200
    json_response = json.loads(response.text)

    assert json_response['version'] == 2
    assert json_response['name'] == update['name']

    response = client.get(f"/bs?id={item_res['id']}")

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
    item_res = json.loads(response.text)

    update = {'id': item_res['id'], 'version': item_res['version'], 'name': '4321'}
    response = client.post('/bs', content=json_bytes(update))
    assert response.status_code == 409


def test_update_nested_resource_through_versioned_resource(client):
    item = {'info': 'toto', 'cs': [{'data': 'nested'}]}
    response = client.post('/ds', content=json_bytes(item))

    assert response.status_code == 201
    res_item = json.loads(response.text)

    update_item = {'cs': [{'data': 'nes_updated'}]}
    update_response = client.put(
        f"/ds/{res_item['id']}_{res_item['version']}",
        content=json_bytes(update_item)
    )
    assert update_response.status_code == 201
    upres_item = json.loads(update_response.text)
    assert upres_item['cs'][0]['data'] == item['cs'][0]['data']
    assert upres_item['cs'][1]['data'] == update_item['cs'][0]['data']


@pytest.mark.xfail(raises=exc.UpdateVersionedError)
def test_update_nested_resource(client):
    item = {'info': 'toto', 'cs': [{'data': 'nested'}]}
    response = client.post('/ds', content=json_bytes(item))

    assert response.status_code == 201
    res_item = json.loads(response.text)

    update_item = {'info': 'titi'}
    update_response = client.put(
        f"/ds/{res_item['id']}_{res_item['version']}",
        content=json_bytes(update_item)
    )


def test_nested_list_after_release_of_parent_resource(client):
    item = {'info': 'toto', 'cs': [{'data': 'nested1'}, {'data': 'nested2'}]}
    response = client.post('/ds', content=json_bytes(item))

    assert response.status_code == 201
    res_item = json.loads(response.text)

    release_item = {'info': 'titi'}
    release_response = client.post(
        f"/ds/{res_item['id']}_{res_item['version']}/release",
        content=json_bytes(release_item)
    )

    assert release_response.status_code == 200
    release_object = json.loads(release_response.text)

    v1 = client.get(f"/ds/{res_item['id']}_{res_item['version']}")
    v2 = client.get(f"/ds/{res_item['id']}_{release_object['version']}")

    assert v1.status_code == 200
    assert v2.status_code == 200

    json_v1 = json.loads(v1.text)
    json_v2 = json.loads(v2.text)
    assert json_v1['cs'] == json_v2['cs']


def test_update_nested_list_after_release_of_parent_resource(client):
    item = {'info': 'toto', 'cs': [{'data': 'nested1'}, {'data': 'nested2'}]}
    response = client.post('/ds', content=json_bytes(item))

    assert response.status_code == 201
    res_item = json.loads(response.text)

    release_item = {'info': 'titi'}
    release_response = client.post(
        f"/ds/{res_item['id']}_{res_item['version']}/release",
        content=json_bytes(release_item)
    )

    assert release_response.status_code == 200
    release_json = json.loads(release_response.text)

    update_nested = {'cs': [{'data': 'nested3'}]}
    update_response = client.put(
        f"/ds/{release_json['id']}_{release_json['version']}",
        content=json_bytes(update_nested)
    )
    oracle_nested = [update_nested['cs'][0]]
    oracle_nested[0].update({'id': 3})

    assert update_response.status_code == 201
    release_json = json.loads(update_response.text)

    assert release_json['cs'] == (res_item['cs'] + oracle_nested)


@pytest.mark.xfail(raises=exc.ReleaseVersionError)
def test_release_twice(client):
    item = {'info': 'toto', 'cs': [{'data': 'nested1'}, {'data': 'nested2'}]}
    response = client.post('/ds', content=json_bytes(item))

    assert response.status_code == 201
    res_item = json.loads(response.text)

    release_item = {'info': 'titi'}
    release_response_1 = client.post(
        f"/ds/{res_item['id']}_{res_item['version']}/release",
        content=json_bytes(release_item)
    )
    assert release_response_1.status_code == 200

    _ = client.post(
        f"/ds/{res_item['id']}_{res_item['version']}/release",
        content=json_bytes(release_item)
    )
