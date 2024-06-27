import requests
import json
import pytest


token: str = ""
token_with_groups: str = ""

user_with_groups = {
    "username": "u_test_wg",
    "password": "1234",
    "groups": [
        {"name": "g_test_wg1"},
        {"name": "g_test_wg2"},
    ]
}


def test_create_user(srv_endpoint, utils):
    """"""
    user = {"username": "u_test", "password": "1234"}
    response = requests.post(f'{srv_endpoint}/users', data=utils.json_bytes(user))
    json_response = json.loads(response.text)

    assert response.status_code == 201
    assert json_response["username"] == user["username"]


def test_create_group(srv_endpoint, utils):
    """"""
    group = {"name": "g_test"}
    response = requests.post(f'{srv_endpoint}/groups', data=utils.json_bytes(group))
    json_response = json.loads(response.text)

    assert response.status_code == 201
    assert json_response["name"] == group["name"]


def test_login_user_on_keycloak_and_get_token(srv_endpoint, utils):
    """"""
    global token
    # Create User
    user = {"username": "u_test", "password": "1234"}
    _ = requests.post(f'{srv_endpoint}/users', data=utils.json_bytes(user))

    token = utils.keycloak_login(srv_endpoint, user['username'], user['password'])

    assert len(token) > 1000
    assert token.startswith('ey')


@pytest.mark.dependency(name="test_login_user_on_keycloak_and_get_token")
def test_authenticated_endpoint(srv_endpoint):
    """"""
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(f'{srv_endpoint}/authenticated', headers=headers)

    assert "u_test" in response.text
    assert "['no_groups']" in response.text


def test_create_user_with_nested_group(srv_endpoint, utils):
    """"""
    user = user_with_groups
    response = requests.post(f'{srv_endpoint}/users', data=utils.json_bytes(user))
    json_response = json.loads(response.text)

    wg1 = requests.get(f'{srv_endpoint}/groups/{user["groups"][0]["name"]}?fields=users')
    wg2 = requests.get(f'{srv_endpoint}/groups/{user["groups"][1]["name"]}?fields=users')
    json_wg1 = json.loads(wg1.text)
    json_wg2 = json.loads(wg2.text)

    assert response.status_code == 201
    assert json_response["username"] == user["username"]
    assert any(user['username'] == wg1user['username'] for wg1user in json_wg1['users'])
    assert any(user['username'] == wg2user['username'] for wg2user in json_wg2['users'])


def test_create_groups_with_nested_users(srv_endpoint, utils):
    """"""
    group = {
        "name": "g_test_wu",
        "users": [
            {"username": "u_test_wu1", "password": "1234"},
            {"username": "u_test_wu2", "password": "1234"},
        ]
    }
    response = requests.post(f'{srv_endpoint}/groups',  data=utils.json_bytes(group))
    json_response = json.loads(response.text)

    wu1 = requests.get(f'{srv_endpoint}/users/{group["users"][0]["username"]}?fields=groups')
    wu2 = requests.get(f'{srv_endpoint}/users/{group["users"][1]["username"]}?fields=groups')

    assert response.status_code == 201
    assert json_response["name"] == group["name"]
    assert group['name'] in wu1.text
    assert group['name'] in wu2.text


@pytest.mark.dependency(name="test_create_user_with_nested_group")
def test_login_and_authenticated_with_groups(srv_endpoint, utils):
    global token_with_groups
    user = user_with_groups
    token_with_groups = utils.keycloak_login(srv_endpoint, user['username'], user['password'])

    headers = {'Authorization': f'Bearer {token_with_groups}'}
    response = requests.get(f'{srv_endpoint}/authenticated', headers=headers)

    assert user_with_groups['username'] in response.text
    assert (
        f"['{user_with_groups['groups'][0]['name']}', "
        f"'{user_with_groups['groups'][1]['name']}']") in response.text
