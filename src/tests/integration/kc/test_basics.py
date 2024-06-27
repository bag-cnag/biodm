import requests


def test_live_endpoint(srv_endpoint):
    """"""
    response = requests.get(f'{srv_endpoint}/live')
    assert response.status_code == 200
    assert response.text == 'live\n'


def test_api_schema(srv_endpoint):
    """"""
    response = requests.get(f'{srv_endpoint}/schema')
    assert response.status_code == 200
    assert "biodm_test_keycloak" in response.text
    assert "0.1.0"               in response.text


def test_login_endpoint(srv_endpoint):
    """"""
    response = requests.get(f'{srv_endpoint}/login')
    assert response.status_code == 200
    assert "protocol/openid-connect/auth" in response.text
    assert "response_type=code" in response.text
    assert "scope=openid" in response.text
