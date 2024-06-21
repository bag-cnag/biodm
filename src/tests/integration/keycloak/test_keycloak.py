import requests
import json
import pytest
from bs4 import BeautifulSoup
from typing import Dict, Any

token: str = ""

def json_bytes(d: Dict[Any, Any]) -> bytes:
    """Encodes python Dict as utf-8 bytes."""
    return json.dumps(d).encode('utf-8')

def keycloak_login(url, username, password):
    # Get and Parse form with bs
    # Courtesy of: https://www.pythonrequests.com/python-requests-keycloak-login/
    with requests.Session() as session:
        form_response = session.get(url)

        soup = BeautifulSoup(form_response.content, 'html.parser')
        form = soup.find('form')
        action = form['action']
        other_fields = {
            i['name']: i.get('value', '')
            for i in form.findAll('input', {'type': 'hidden'})
        }

        return session.post(action, data={
            'username': username,
            'password': password,
            **other_fields,
        }, allow_redirects=True)


def test_create_user(srv_endpoint):
    """"""
    user = {"username": "u_test", "password": "1234"}
    response = requests.post(f'{srv_endpoint}/users', data=json_bytes(user))
    json_response = json.loads(response.text)

    assert response.status_code == 201
    assert json_response["username"] == user["username"]


def test_create_group(srv_endpoint):
    """"""
    group = {"name": "g_test"}
    response = requests.post(f'{srv_endpoint}/groups', data=json_bytes(group))
    json_response = json.loads(response.text)

    assert response.status_code == 201
    assert json_response["name"] == group["name"]


def test_login_user_on_keycloak_and_get_token(srv_endpoint):
    """"""
    global token
    # Create User
    user = {"username": "u_test", "password": "1234"}
    _ = requests.post(f'{srv_endpoint}/users', data=json_bytes(user))

    # Get login page
    login_url = requests.get(f'{srv_endpoint}/login')
    response = keycloak_login(login_url.text, user['username'], user['password'])
    token = response.text.rstrip('\n')

    assert response.status_code == 200
    assert len(token) > 1000
    assert token.startswith('ey')


@pytest.mark.dependency(name="test_login_user_on_keycloak_and_get_token")
def test_authenticated_endpoint(srv_endpoint):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(f'{srv_endpoint}/authenticated', headers=headers)

    assert "u_test" in response.text
    assert "['no_groups']" in response.text


# def test_create_user_with_nested_groups(client):
#     """"""
#     user = {"username": "u_test", "password": "1234"}
#     response = client.post('/users', content=json_bytes(user))
#     json_response = json.loads(response.text)

#     assert response.status_code == 201
#     assert json_response["username"] == user["username"]


# def test_create_groups_with_nested_users(client):
#     """"""
#     group = {"name": "g_test"}
#     response = client.post('/groups', content=json_bytes(group))
#     json_response = json.loads(response.text)

#     assert response.status_code == 201
#     assert json_response["username"] == group["username"]
