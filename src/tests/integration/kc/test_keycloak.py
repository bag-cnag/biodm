from httpx import head
import requests
import json
import pytest
from typing import Dict

token: str = ""
token_with_groups: str = ""
user_with_groups = {
    "username": "u_test_wg",
    "password": "1234",
    "groups": [
        {"path": "g_test_wg1"},
        {"path": "g_test_wg2"},
    ]
}
user_test: Dict[str, str] = {"username": "u_test", "password": "1234", "firstName": "john", "lastName": "doe"}


def test_create_user(srv_endpoint, utils, admin_header):
    """"""
    response = requests.post(
        f'{srv_endpoint}/users',
        data=utils.json_bytes(user_test),
        headers=admin_header
    )

    assert response.status_code == 201
    json_response = json.loads(response.text)

    assert json_response["username"] == user_test["username"]
    assert json_response["firstName"] == user_test["firstName"]
    assert json_response["lastName"] == user_test["lastName"]


@pytest.mark.dependency(name="test_create_user")
def test_update_user(srv_endpoint, utils, admin_header):
    update = {"username": user_test['username'], "firstName": "jack"}
    response = requests.post(
        f'{srv_endpoint}/users',
        data=utils.json_bytes(update),
        headers=admin_header
    )

    assert response.status_code == 201
    json_response = json.loads(response.text)

    assert json_response["username"] == user_test["username"]
    assert json_response["username"] == update["username"]
    assert json_response["firstName"] == update["firstName"]
    assert json_response["lastName"] == user_test["lastName"]


def test_create_group(srv_endpoint, utils, admin_header):
    """"""
    group = {"path": "g_test"}
    response = requests.post(
        f'{srv_endpoint}/groups',
        data=utils.json_bytes(group),
        headers=admin_header
    )
    json_response = json.loads(response.text)
    assert response.status_code == 201
    assert json_response["path"] == group["path"]


def test_login_user_on_keycloak_and_get_token(srv_endpoint, utils, admin_header):
    """"""
    global token
    # Create User
    user = {"username": "u_test", "password": "1234"}
    response = requests.post(
        f'{srv_endpoint}/users',
        data=utils.json_bytes(user),
        headers=admin_header
    )
    assert response.status_code == 201

    token = utils.keycloak_login(srv_endpoint, user['username'], user['password'])

    assert len(token) > 1000
    assert token.startswith('ey')


@pytest.mark.dependency(name="test_login_user_on_keycloak_and_get_token")
def test_authenticated_endpoint(srv_endpoint):
    """"""
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(f'{srv_endpoint}/authenticated', headers=headers)

    userinfo = json.loads(response.text)
    assert "u_test" == userinfo["username"]
    assert ['no_groups'] == userinfo["groups"]


def test_create_user_with_nested_group(srv_endpoint, utils, admin_header):
    """"""
    user = user_with_groups
    response = requests.post(
        f'{srv_endpoint}/users',
        data=utils.json_bytes(user),
        headers=admin_header
    )
    json_response = json.loads(response.text)

    wg1 = requests.get(f'{srv_endpoint}/groups/{user["groups"][0]["path"]}?fields=users')
    wg2 = requests.get(f'{srv_endpoint}/groups/{user["groups"][1]["path"]}?fields=users')
    json_wg1 = json.loads(wg1.text)
    json_wg2 = json.loads(wg2.text)

    assert response.status_code == 201
    assert json_response["username"] == user["username"]
    assert any(user['username'] == wg1user['username'] for wg1user in json_wg1['users'])
    assert any(user['username'] == wg2user['username'] for wg2user in json_wg2['users'])


def test_create_groups_with_nested_users(srv_endpoint, utils, admin_header):
    """"""
    group = {
        "path": "g_test_wu",
        "users": [
            {"username": "u_test_wu1", "password": "1234"},
            {"username": "u_test_wu2", "password": "1234"},
        ]
    }
    response = requests.post(
        f'{srv_endpoint}/groups',
        data=utils.json_bytes(group),
        headers=admin_header
    )
    json_response = json.loads(response.text)

    wu1 = requests.get(f'{srv_endpoint}/users/{group["users"][0]["username"]}?fields=groups')
    wu2 = requests.get(f'{srv_endpoint}/users/{group["users"][1]["username"]}?fields=groups')

    assert response.status_code == 201
    assert json_response["path"] == group["path"]
    assert group['path'] in wu1.text
    assert group['path'] in wu2.text


@pytest.mark.dependency(name="test_create_user_with_nested_group")
def test_login_and_authenticated_with_groups(srv_endpoint, utils):
    global token_with_groups
    user = user_with_groups
    token_with_groups = utils.keycloak_login(srv_endpoint, user['username'], user['password'])

    headers = {'Authorization': f'Bearer {token_with_groups}'}
    response = requests.get(f'{srv_endpoint}/authenticated', headers=headers)

    userinfo = json.loads(response.text)

    assert userinfo['username'] == user_with_groups['username']
    assert userinfo['groups'] == [group['path'] for group in user_with_groups['groups']]


def test_create_groups_with_parent(srv_endpoint, utils, admin_header):
    parent = {
        "path": "parent"
    }
    child1 = {
        "path": f"{parent['path']}__child1"
    }
    child2 = {
        "path": f"{parent['path']}__child2"
    }
    parent_response = requests.post(
        f'{srv_endpoint}/groups',
        data=utils.json_bytes(parent),
        headers=admin_header
    )
    child_response = requests.post(
        f'{srv_endpoint}/groups',
        data=utils.json_bytes(child1),
        headers=admin_header
    )
    child2_response = requests.post(
        f'{srv_endpoint}/groups',
        data=utils.json_bytes(child2),
        headers=admin_header
    )

    assert parent_response.status_code == 201
    assert child_response.status_code == 201
    assert child2_response.status_code == 201

    json_child = json.loads(child_response.text)
    assert json_child['path'] == child1['path']
    assert json_child['parent']['path'] == parent['path']

    search_parent = requests.get(f"{srv_endpoint}/groups?path={parent['path']}&fields=children,parent")
    assert search_parent.status_code == 200

    json_parent = json.loads(search_parent.text)
    assert len(json_parent) == 1
    json_parent = json_parent[0]

    assert json_parent['parent'] is None
    assert len(json_parent['children']) == 2
    assert json_parent['children'][0]['path'] == child1['path']
    assert json_parent['children'][1]['path'] == child2['path']
