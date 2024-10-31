import json
import os
import pytest
import requests
from typing import Dict, Any

from bs4 import BeautifulSoup


ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = '1234'


@pytest.fixture(scope="session", autouse=True)
def srv_endpoint():
    key = 'API_ENDPOINT'

    if key in os.environ:
        return os.environ[key]
 
    return "http://127.0.0.1:8000" # default config.


class Utils:
    """Util methods as fixture."""
    @staticmethod
    def json_bytes(d: Dict[Any, Any]) -> bytes:
        """Encodes python Dict as utf-8 bytes."""
        return json.dumps(d).encode('utf-8')

    @staticmethod
    def keycloak_login(srv_endpoint, username, password):
        # Get and Parse form with bs
        # Courtesy of: https://www.pythonrequests.com/python-requests-keycloak-login/
        login_url = requests.get(f'{srv_endpoint}/login')
        with requests.Session() as session:
            form_response = session.get(login_url.text)

            soup = BeautifulSoup(form_response.content, 'html.parser')
            form = soup.find('form')
            action = form['action']
            other_fields = {
                i['name']: i.get('value', '')
                for i in form.findAll('input', {'type': 'hidden'})
            }

            response = session.post(action, data={
                'username': username,
                'password': password,
                **other_fields,
            }, allow_redirects=True)

            assert response.status_code == 200

            return response.text.rstrip('\n')


@pytest.fixture(scope="session")
def utils():
    return Utils


@pytest.fixture(scope="session")
def admin_header(srv_endpoint, utils):
    """Set header for admin token bearer."""
    admin_token = utils.keycloak_login(srv_endpoint, ADMIN_USERNAME, ADMIN_PASSWORD)
    return {'Authorization': f'Bearer {admin_token}'}
