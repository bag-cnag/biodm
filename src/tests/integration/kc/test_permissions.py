import json
import pytest
import requests
from typing import Any, Dict
from uuid import uuid4

session_id = uuid4()

token_user1: str = ""
token_user2: str = ""
token_user2_child: str = ""


project_2_id: int
project_2_read_id: int


user1: Dict[str, str] = {
    "username":f"u_{session_id}_1",
    "password": "1234",
}


user2: Dict[str, str] = {
    "username": f"u_{session_id}_2",
    "password": "1234",
}


user2_child: Dict[str, str] = {
    "username": f"u_{session_id}_2_child",
    "password": "1234"
}


user3: Dict[str, str] = {
    "username": f"u_{session_id}_3",
    "password": "1234",
}


group1: Dict[str, str] = {
    "path":f"g_{session_id}_1",
    "users":[user1],
}


group2: Dict[str, str] = {
    "path":f"g_{session_id}_2",
    "users":[user2],
}


group2_child: Dict[str, str] = {
    "path": group2['path'] + "__child",
    "users": [user2_child],
}


group3: Dict[str, str] = {
    "path":f"g_{session_id}_3",
    "users":[user3],
}


project1: Dict[str, Any] = {
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


project2: Dict[str, Any] = {
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


dataset1: Dict[str, Any] = {
    "name": "ds_test",
    "project_id": "1",
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


dataset2: Dict[str, Any] = {
    "name": "ds_test_parent",
    "project_id": "2",
    "contact": {
        "username": user2['username']
    },
}


public_project: Dict[str, Any] = {
    "name": f"pr_{session_id}_public",
    "datasets": [
        {
            "name": f"ds_{session_id}_public",
            "contact": {
                "username": user1['username']
            },
            "tags": [{"name": "bip"},{"name": "bap"}]
        },
    ]
}


tag: Dict[str, str] = {"name": "xyz"}


def test_create_data_and_login(srv_endpoint, utils, admin_header):
    global token_user1, token_user2, token_user2_child, project_2_id, project_2_read_id

    groups = requests.post(
        f"{srv_endpoint}/groups",
        data=utils.json_bytes(
            [group1, group2, group3, group2_child]
        ),
        headers=admin_header
    )
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


    json_pro = json.loads(projects.text)
    assert len(json_pro) == 2
    project_2_id = json_pro[-1]['id']
    project_2_read_id = json_pro[-1]['perm_datasets']['read']['id']


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
    assert response1.status_code == 200

    response2 = requests.get(
        f'{srv_endpoint}/datasets',
        headers=headers2
    )
    assert response2.status_code == 200


    json_response2 = json.loads(response2.text)
    json_response1 = json.loads(response1.text)


    assert len(json_response1) == 1
    assert str(json_response1[0]['name']) == str(dataset1['name'])
    assert str(json_response1[0]['project_id']) == str(dataset1['project_id'])
    assert json_response2 == []


@pytest.mark.dependency(name="test_create_data_and_login")
def test_create_public_data(srv_endpoint, utils):
    headers1 = {'Authorization': f'Bearer {token_user1}'}

    response = requests.post(
        f'{srv_endpoint}/projects',
        data=utils.json_bytes(public_project),
        headers=headers1
    )

    assert response.status_code == 201


@pytest.mark.dependency(name="test_create_public_data")
def test_read_public_data(srv_endpoint):
    """Getting datasets without explicit fields will yield dataset, without its tags."""
    response = requests.get(f'{srv_endpoint}/datasets')

    json_response = json.loads(response.text)

    assert response.status_code == 200
    assert len(json_response) == 1
    assert json_response[0]['name'] == public_project['datasets'][0]['name']
    assert 'tags' not in json_response[0]


@pytest.mark.dependency(name="test_create_public_data")
def test_read_restricted_field_from_public_data(srv_endpoint):
    """Getting datasets asking explicitely for its tags (which are protected) will fail."""
    response = requests.get(f'{srv_endpoint}/datasets?fields=tags')

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

@pytest.mark.dependency(name="test_create_data_and_login")
def test_add_to_project_permission(srv_endpoint, utils):
    project_update = {
        "perm_datasets": {
            "read": {
                "id": project_2_read_id,
                "groups": [
                    {"path": group3['path']},
                ]
            }
        }
    }

    # Will now contain both group2 from creation and group3 from update
    response = requests.put(
        f'{srv_endpoint}/projects/{project_2_id}',
        data=utils.json_bytes(project_update)
    )

    assert response.status_code == 201
    json_response = json.loads(response.text)
    assert json_response['perm_datasets']['read']['id'] == project_2_read_id

    groups_oracle = [
        {"path": group2['path']},
        {"path": group3['path']}
    ]
    assert json_response['perm_datasets']['read']['groups'] == groups_oracle


@pytest.mark.dependency(name="test_add_to_project_permission")
def test_change_project_permission(srv_endpoint, utils):
    project_update = {
        "perm_datasets": {
            "read": {
                "groups": [
                    {"path": group1['path']},
                ]
            }
        }
    }

    response = requests.put(
        f'{srv_endpoint}/projects/{project_2_id}',
        data=utils.json_bytes(project_update)
    )

    assert response.status_code == 201
    json_response = json.loads(response.text)
    assert json_response['perm_datasets']['read']['id'] != project_2_read_id
    assert (
        json_response['perm_datasets']['read']['groups'] ==
        project_update["perm_datasets"]["read"]["groups"]
    )


def test_create_tag_no_auth(srv_endpoint, utils):
    response = requests.post(f'{srv_endpoint}/tags', data=utils.json_bytes(tag))

    assert response.status_code == 511


@pytest.mark.dependency(name="test_create_data_and_login")
def test_create_tag_auth(srv_endpoint, utils):
    headers = {'Authorization': f'Bearer {token_user1}'}

    response = requests.post(f'{srv_endpoint}/tags', data=utils.json_bytes(tag), headers=headers)

    assert response.status_code == 201

    json_tag = json.loads(response.text)
    assert tag == json_tag


@pytest.mark.dependency(name="test_create_tag_auth")
def test_read_tag_no_auth(srv_endpoint):
    response = requests.get(f'{srv_endpoint}/tags/{tag["name"]}')

    assert response.status_code == 511


@pytest.mark.dependency(name="test_create_tag_auth")
def test_read_tag_auth(srv_endpoint, utils):
    headers = {'Authorization': f'Bearer {token_user1}'}
    response = requests.get(f'{srv_endpoint}/tags/{tag["name"]}', data=utils.json_bytes(tag), headers=headers)

    assert response.status_code == 200

    json_tag = json.loads(response.text)
    assert tag == json_tag
