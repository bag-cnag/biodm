import json
import pytest
import requests
from uuid import uuid4

session_id = uuid4()

token_user1: str = ""
token_user2: str = ""
token_user2_child: str = ""

user1 = {
    "username":f"u_{session_id}_1",
    "password": "1234",
}

user2 = {
    "username": f"u_{session_id}_2",
    "password": "1234",
}

user2_child = {
    "username": f"u_{session_id}_2_child",
    "password": "1234"
}

# user2_grandchild = {
#     "username": f"u_{session_id}_2_grandchild",
# }

user3 = {
    "username": f"u_{session_id}_3",
    "password": "1234",
}

group1 = {
    "path":f"g_{session_id}_1",
    "users":[user1],
}

group2 = {
    "path":f"g_{session_id}_2",
    "users":[user2],
}

group2_child = {
    "path": group2['path'] + "__child",
    "users": [user2_child],
}

# group2_grandchild = {
#     "path": group2_child['path'] + "__grandchild",
#     "users":[user2_grandchild],
# }

group3 = {
    "path":f"g_{session_id}_3",
    "users":[user3],
}

project1 = {
    "name": f"pr_{session_id}_1",
    "perm_datasets": {
        "read": {
            "groups": [
                {"path": group1['path']},
                {"path": group3['path']},
            ]
        },
        "write": {
            "groups": [
                {"path": group1['path']},
                {"path": group3['path']},
            ]
        },
    }
}

project2 = {
    "name": f"pr_{session_id}_2",
    "perm_datasets": {
        "read": {
            "groups": [
                {"path": group2['path']}
            ]
        },
        "write": {
            "groups": [
                {"path": group2['path']}
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
                {"path": group3['path']},
            ]
        },
        "read": {
            "groups": [
                {"path": group3['path']},
            ]
        }
    }
}


dataset2 = {
    "name": "ds_test_parent",
    "id_project": "2",
    "contact": {
        "username": user2['username']
    },
}


public_project = {
    "name": f"pr_{session_id}_public",
    "datasets": [
        {
            "name": f"ds_{session_id}_public",
            "contact": {
                "username": user1['username']
            },
        },
    ]
}


def test_create_data_and_login(srv_endpoint, utils):
    global token_user1, token_user2, token_user2_child

    groups = requests.post(f"{srv_endpoint}/groups", data=utils.json_bytes(
        [
            group1, group2, group3, group2_child,# group2_grandchild
        ]
    ))
    projects = requests.post(f"{srv_endpoint}/projects", data=utils.json_bytes(
        [
            project1, project2
        ]
    ))

    assert groups.status_code == 201
    assert projects.status_code == 201

    token_user1 = utils.keycloak_login(srv_endpoint, user1['username'], user1['password'])
    token_user2 = utils.keycloak_login(srv_endpoint, user2['username'], user2['password'])
    token_user2_child = utils.keycloak_login(
        srv_endpoint, user2_child['username'], user2_child['password'])


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


def test_create_public_data(srv_endpoint, utils):
    response = requests.post(
        f'{srv_endpoint}/projects',
        data=utils.json_bytes(public_project),
    )

    assert response.status_code == 201


@pytest.mark.dependency(name="test_create_public_data")
def test_read_public_data(srv_endpoint, utils):
    """Getting datasets without explicit fields will yield dataset, without its tags."""
    response = requests.get(
        f'{srv_endpoint}/datasets',
        data=utils.json_bytes(public_project),
    )

    json_response = json.loads(response.text)

    assert response.status_code == 200
    assert len(json_response) == 1
    assert json_response[0]['name'] == public_project['datasets'][0]['name']
    assert 'tags' not in json_response[0]


@pytest.mark.dependency(name="test_create_public_data")
def test_read_restricted_field_from_public_data(srv_endpoint, utils):
    """Getting datasets asking explicitely for its tags (which are protected) will fail."""
    response = requests.get(
        f'{srv_endpoint}/datasets?fields=tags',
        data=utils.json_bytes(public_project),
    )

    assert response.status_code == 511


@pytest.mark.dependency(name="test_create_data_and_login")
def test_create_from_child_group(srv_endpoint, utils):
    """User 2 child, write perm on Project 2 through parent."""
    global token_user2_child

    headers = {'Authorization': f'Bearer {token_user2_child}'}
    response = requests.post(
        f'{srv_endpoint}/datasets',
        data=utils.json_bytes(dataset2),
        headers=headers
    )

    assert response.status_code == 201
