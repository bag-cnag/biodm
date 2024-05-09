import pytest
import json
# from urllib import response
from .app import app_test_client, json_bytes

@pytest.mark.asyncio
async def test_resource_schema():
    async with app_test_client() as client:
        response = await client.get('/as/schema/')
        assert response.status_code == 200
        json_response = json.loads(response.text)
        assert "/" in json_response['paths']
        assert "/search/" in json_response['paths']

@pytest.mark.asyncio
async def test_create_unary_resource():
    async with app_test_client() as client:
        response = await client.post('/bs/', content=json_bytes({'name': 'test'}))
        assert response.status_code == 201
        assert "id" in response.text
        assert "test" in response.text
