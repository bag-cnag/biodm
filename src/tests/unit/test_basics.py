def test_live_endpoint(client):
    """"""
    response = client.get('/live')
    assert response.status_code == 200
    assert response.text == 'live\n'


def test_api_schema(client):
    """"""
    response = client.get('/schema')
    assert response.status_code == 200
    assert "biodm_test" in response.text
    assert "0.1.0"      in response.text


# def test_login_endpoint(client_args):
#     with TestClient(**client_args) as client:
#         response = client.get('/login')
#         assert response.status_code == 200
