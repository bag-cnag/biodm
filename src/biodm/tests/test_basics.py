import pytest
import json
# from urllib import response
from .app import app_test_client

@pytest.mark.asyncio
async def test_live_endpoint():
    # async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
    async with app_test_client() as client:
        response = await client.get('/live')
        assert response.status_code == 200
        assert response.text == 'live\n'

@pytest.mark.asyncio
async def test_api_schema():
    async with app_test_client() as client:
        response = await client.get('/schema')
        assert response.status_code == 200
        assert "biodm_test" in response.text
        assert "0.1.0"      in response.text

# def test_controllers_schemas():
# TODO:
# def test schema
# def test_login_endpoint():
# def test_users
# def test_groups
