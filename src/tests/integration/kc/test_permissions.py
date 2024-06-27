import json
import pytest
import requests
from uuid import uuid4

session_id = uuid4()

token_user1: str = ""
token_user2: str = ""
token_user3: str = ""

user1 = {
    "username":f"u_{session_id}_1",
    "password": "1234",
}

user2 = {
    "username": f"u_{session_id}_2",
    "password": "1234",
}

user3 = {
    "username": f"u_{session_id}_3",
    "password": "1234",
}

group1 = {
    "name":f"g_{session_id}_1",
    "users":[user1],
}

group2 = {
    "name":f"g_{session_id}_2",
    "users":[user2],
}

group3 = {
    "name":f"g_{session_id}_3",
    "users":[user3],
}

project1 = {
    "name": f"pr_{session_id}_1",
    "perm_datasets": {
        "read": {
            "groups": [
                {"name": group1['name']},
                {"name": group3['name']},
            ]
        },
        "write": {
            "groups": [
                {"name": group1['name']},
                {"name": group3['name']},
            ]
        },
    }
}

project2 = {
    "name": f"pr_{session_id}_2",
    "perm_datasets": {
        "read": {
            "groups": [
                {"name": group2['name']}
            ]
        },
        "write": {
            "groups": [
                {"name": group2['name']}
            ]
        }
    }
}


dataset1 = {
    "name": "ds_test",
    "id_project": "1",
    "contact": {
        "username": user1['username']
    },
    "perm_files": {
        "write": {
            "groups": [
                {"name": group3['name']},
            ]
        },
        "read": {
            "groups": [
                {"name": group3['name']},
            ]
        }
    }
}


def test_create_data_and_login(srv_endpoint, utils):
    global token_user1, token_user2

    groups = requests.post(f"{srv_endpoint}/groups", data=utils.json_bytes([group1, group2, group3]))
    projects = requests.post(f"{srv_endpoint}/projects", data=utils.json_bytes([project1, project2]))

    assert groups.status_code == 201
    assert projects.status_code == 201

    token_user1 = utils.keycloak_login(srv_endpoint, user1['username'], user1['password'])
    token_user2 = utils.keycloak_login(srv_endpoint, user2['username'], user2['password'])


@pytest.mark.dependency(name="test_create_data_and_login")
def test_create_dataset(srv_endpoint, utils):
    """User 1, write perm on Project 1."""
    global token_user1

    headers = {'Authorization': f'Bearer {token_user1}'}
    response = requests.post(
        f'{srv_endpoint}/datasets',
        data=utils.json_bytes(dataset1),
        headers=headers
    )

    assert response.status_code == 201


@pytest.mark.dependency(name="test_create_data_and_login")
def test_create_dataset_no_write_perm(srv_endpoint, utils):
    """User 2, no write perm on Project 1."""
    global token_user2

    headers = {'Authorization': f'Bearer {token_user2}'}
    response = requests.post(
        f'{srv_endpoint}/datasets',
        data=utils.json_bytes(dataset1),
        headers=headers
    )

    assert response.status_code == 511


@pytest.mark.dependency(name="test_create_dataset")
def test_read_dataset_no_read_perm(srv_endpoint):
    """User 2 should not see inserted dataset from Project 1."""
    global token_user1, token_user2

    headers1 = {'Authorization': f'Bearer {token_user1}'}
    headers2 = {'Authorization': f'Bearer {token_user2}'}
    
    response1 = requests.get(
        f'{srv_endpoint}/datasets',
        headers=headers1
    )
    json_response1 = json.loads(response1.text)
    response2 = requests.get(
        f'{srv_endpoint}/datasets',
        headers=headers2
    )
    json_response2 = json.loads(response2.text)


    assert response1.status_code == 200
    assert response2.status_code == 200
    assert len(json_response1) == 1
    assert str(json_response1[0]['name']) == str(dataset1['name'])
    assert str(json_response1[0]['id_project']) == str(dataset1['id_project'])
    assert json_response2 == []
