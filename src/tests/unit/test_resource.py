from copy import deepcopy
import time
import pytest
import json

from biodm import exceptions as exc
from marshmallow import exceptions as me
from biodm.utils.utils import json_bytes, json_response


def test_resource_schema(client):
    """"""
    response = client.get('/as/schema')
    json_response = json.loads(response.text)

    assert response.status_code == 200
    assert "/as" in json_response['paths']
    assert "/as/schema" in json_response['paths']
    assert "/as/{id}" in json_response['paths']


def test_create_unary_resource(client):
    """"""
    item = {'name': 'test'}
    response = client.post('/bs', content=json_bytes(item))

    assert response.status_code == 201
    assert "id" in response.text
    assert "test" in response.text


def test_create_composite_resource(client):
    item = {
        'x': 1,
        'y': 2,
        'c': {'data': '1234'},
        'bs': [{'name': 'bip'},{'name': 'bap'},{'name': 'bop'}]
    }
    oracle = deepcopy(item)
    oracle['id'] = 1
    oracle['id_c'] = 1
    oracle['c']['id'] = 1
    for i, x in enumerate(oracle['bs']):
        x['id'] = i+1
        x['version'] = 1

    response = client.post('/as', content=json_bytes(item))
    json_response = json.loads(response.text)

    assert response.status_code == 201
    assert json_response['x'] == oracle['x']
    assert json_response['y'] == oracle['y']
    assert json_response['c'] == oracle['c']
    # May be in different orders.
    oracle['bs'].sort(key=lambda x: x['id'])
    json_response['bs'].sort(key=lambda x: x['id'])

    for bor, bres in zip(oracle['bs'],json_response['bs']):
        bor['id'] == bres['id']
        bor['version'] == bres['version']
        bor['name'] == bres['name']


@pytest.mark.xfail(raises=exc.PayloadEmptyError)
def test_create_empty_data(client):
    client.post('/as', content=json_bytes({}))


@pytest.mark.xfail(raises=me.ValidationError)
def test_create_wrong_data(client):
    client.post('/as', content=json_bytes({'wrong': False}))


def test_read_resource(client):
    item = {'x': 1, 'y': 2, 'c': {'data': '1234'},}

    _ = client.post('/as', content=json_bytes(item))
    response = client.get('/cs/1')
    json_response = json.loads(response.text)

    assert response.status_code == 200
    assert json_response['data'] == '1234'


@pytest.mark.xfail(raises=exc.FailedRead)
def test_missing_resource(client):
    client.get('/cs/1')


def test_readall_resource(client):
    item1 = {'x': 1, 'y': 2, 'bs': [{'name': 'bip'},{'name': 'bap'},]}
    item2 = {'x': 3, 'y': 4, 'bs': [{'name': 'tit'},{'name': 'tat'},]}

    _ = client.post('/as', content=json_bytes([item1, item2]))
    response = client.get('/bs')
    json_response = json.loads(response.text)

    assert response.status_code == 200
    assert len(json_response) == 4
    for b in item1['bs'] + item2['bs']:
        assert any(b['name'] == jr['name'] for jr in json_response)


def test_filter_resource_wildcard(client):
    item1 = {'x': 1, 'y': 2, 'bs': [{'name': 'bip'},{'name': 'bap'},]}
    item2 = {'x': 3, 'y': 4, 'bs': [{'name': 'tit'},{'name': 'tat'},]}

    _ = client.post('/as', content=json_bytes([item1, item2]))
    response = client.get('/bs?name=b*')
    json_response = json.loads(response.text)

    assert response.status_code == 200
    assert len(json_response) == 2
    for b in item1['bs']:
        assert any(b['name'] == jr['name'] for jr in json_response)
    for b in item2['bs']:
        assert not any(b['name'] == jr['name'] for jr in json_response)


def test_filter_resource_values(client):
    item1 = {'x': 1, 'y': 2, 'bs': [{'name': 'bip'},{'name': 'bap'},]}
    item2 = {'x': 3, 'y': 4, 'bs': [{'name': 'tit'},{'name': 'tat'},]}

    _ = client.post('/as', content=json_bytes([item1, item2]))
    response = client.get('/bs?name=bip,tat')
    json_response = json.loads(response.text)

    assert response.status_code == 200
    assert len(json_response) == 2
    for jr in json_response:
        assert jr['name'] in ('bip', 'tat')


def test_filter_resource_op(client):
    item1 = {'x': 1, 'y': 2, 'bs': [{'name': 'bip'},{'name': 'bap'},]}
    item2 = {'x': 3, 'y': 4, 'bs': [{'name': 'tit'},{'name': 'tat'},]}

    _ = client.post('/as', content=json_bytes([item1, item2]))
    response = client.get('/as?x.lt(2)')
    json_response = json.loads(response.text)

    assert json_response

    json_response = next(iter(json.loads(response.text)))

    assert response.status_code == 200
    assert json_response['x'] == 1
    assert json_response['y'] == 2


def test_filter_resource_min_max(client):
    item1 = {'x': 1, 'y': 2}
    item2 = {'x': 3, 'y': 4}
    item3 = {'x': 5, 'y': 6}

    res_post = client.post('/as', content=json_bytes([item1, item2, item3]))
    assert res_post.status_code == 201

    res_min = client.get('/as?y.min()')
    res_max = client.get('/as?x.max()')

    assert res_min.status_code == 200
    assert res_max.status_code == 200

    json_min = next(iter(json.loads(res_min.text)))
    json_max = next(iter(json.loads(res_max.text)))

    assert json_min['x'] == item1['x'] and json_min['y'] == item1['y']
    assert json_max['x'] == item3['x'] and json_max['y'] == item3['y']


def test_filter_resource_min_and_cond(client):
    item1 = {'x': 1, 'y': 2}
    item2 = {'x': 3, 'y': 4}
    item3 = {'x': 5, 'y': 6}

    res_post = client.post('/as', content=json_bytes([item1, item2, item3]))
    assert res_post.status_code == 201

    res_filter = client.get('/as?y=4&y.min()')
    assert res_filter.status_code == 200
    assert json.loads(res_filter.text) == []


def test_filter_resource_nested(client):
    item1 = {'x': 1, 'y': 2, 'c': {'data': '1234'},}
    item2 = {'x': 3, 'y': 4, 'c': {'data': '4321'},}

    _ = client.post('/as', content=json_bytes([item1, item2]))
    response = client.get('/as?c.data=4321')
    json_response = next(iter(json.loads(response.text)))

    assert response.status_code == 200
    assert json_response['x'] == 3
    assert json_response['y'] == 4


def test_filter_resource_with_fields(client):
    item1 = {'x': 1, 'y': 2, 'c': {'data': '1234'},}
    item2 = {'x': 3, 'y': 4, 'c': {'data': '4321'},}

    _ = client.post('/as', content=json_bytes([item1, item2]))
    response = client.get('/as?x=1&fields=x,c')
    json_response = next(iter(json.loads(response.text)))

    assert response.status_code == 200
    assert 'x' in json_response and json_response['x'] == 1
    assert 'y' not in json_response
    assert 'c' in json_response and json_response['c']['data'] == '1234'


@pytest.mark.xfail(raises=exc.EndpointError)
def test_filter_wrong_op(client):
    item = {'x': 1, 'y': 2, 'bs': [{'name': 'bip'}, {'name': 'bap'},]}

    client.post('/as', content=json_bytes(item))
    client.get('/as?x.lt=2')


@pytest.mark.xfail(raises=exc.QueryError)
def test_filter_wrong_wildcard(client):
    item = {'x': 1, 'y': 2, 'bs': [{'name': 'bip'}, {'name': 'bap'},]}

    client.post('/as', content=json_bytes(item))
    client.get('/as?y=2*')


@pytest.mark.xfail(raises=exc.EndpointError)
def test_filter_op_on_string(client):
    item = {'x': 1, 'y': 2, 'bs': [{'name': 'bip'}, {'name': 'bap'},]}

    client.post('/as', content=json_bytes(item))
    client.get('/bs?name.gt(2)')


def test_update_unary_resource(client):
    item = {'data': 'test'}
    cr_response = client.post('/cs', content=json_bytes(item))
    item_id = json.loads(cr_response.text)['id']

    up_response = client.put(f'/cs/{item_id}', content=json_bytes({'data': 'modified'}))
    json_response = json.loads(up_response.text)

    assert up_response.status_code == 201
    assert json_response['id'] == item_id
    assert json_response['data'] == 'modified'


def test_update_composite_resource(client):
    item = {'x': 1, 'y': 2, 'c': {'data': 'bip'}}
    cr_response = client.post('/as', content=json_bytes(item))
    item_id = json.loads(cr_response.text)['id']

    c_oracle = {'data': 'bop'}
    up_response = client.put(f'/as/{item_id}', content=json_bytes(
        {
            'x': 3,
            'c': c_oracle
        }
    ))
    json_response = json.loads(up_response.text)

    assert up_response.status_code == 201
    assert json_response['id'] == item_id
    assert json_response['x'] == 3
    assert json_response['c']['id'] == 2
    assert json_response['c']['data'] == c_oracle['data']



def test_read_nested_collection(client):
    item = {'x': 1, 'y': 2, 'bs': [{'name': 'bip'}, {'name': 'bap'},]}

    create = client.post('/as', content=json_bytes(item))
    assert create.status_code == 201
    response = client.get('/as/1/bs')
    assert response.status_code == 200

    json_response = json.loads(response.text)
    assert len(json_response) == 2
    for i, b in enumerate(json_response):
        assert item['bs'][i]['name'] == b['name']


@pytest.mark.xfail(raises=exc.EndpointError)
def test_read_nested_collection_wrong_name(client):
    item = {'x': 1, 'y': 2, 'bs': [{'name': 'bip'}, {'name': 'bap'},]}

    create = client.post('/as', content=json_bytes(item))
    assert create.status_code == 201

    _ = client.get('/as/1/bsss')


def test_delete_resource(client):
    item = {'x': 1, 'y': 2,}

    _ = client.post('/as', content=json_bytes(item))
    response = client.delete('/as/1')

    assert response.status_code == 200
    assert "Deleted." in response.text


def test_update_resource_through_create(client):
    item = {'data': '1234'}

    response = client.post('/cs', content=json_bytes(item))
    assert response.status_code == 201

    update = {'id': '1', 'data': '4321'}
    response = client.post('/cs', content=json_bytes(update))
    assert response.status_code == 201

    response = client.get('/cs')
    assert response.status_code == 200

    json_response = json.loads(response.text)
    assert len(json_response) == 1
    assert json_response[0]['data'] == update['data']

def test_requesting_count_in_filter(client):
    items = [{'name': 'bip'}, {'name': 'bap'}, {'name': 'bop'}]
    response = client.post('/bs', content=json_bytes(items))
    assert response.status_code == 201

    findall = client.get('/bs?count=True')
    assert findall.status_code == 200
    assert 'x-total-count' in findall.headers
    assert int(findall.headers.get('x-total-count')) == 3
