import json
import pytest
import requests
import filecmp
from pathlib import Path

from typing import Dict

HASH_FUNC = 'sha256'
project = {"name": "pr_test"}
dataset = {
    "name": "ds_test",
    "id_project": "1",
    "contact": {
        "username": "u_test"
    },
}
file = {
    "filename": "test",
    "extension": "h5ad",
    "id_dataset": "1",
    "version_dataset": "1"
}

file_name = "test.h5ad"
file_path = Path(__file__).parent / file_name
upload_form: Dict[str, str]


def test_create_project_dataset(srv_endpoint, utils):
    rpr = requests.post(f"{srv_endpoint}/projects", data=utils.json_bytes(project))
    rds = requests.post(f"{srv_endpoint}/datasets", data=utils.json_bytes(dataset))


    assert rpr.status_code == 201
    assert rds.status_code == 201


@pytest.mark.dependency(name="test_create_project_dataset")
def test_create_file(srv_endpoint, utils):
    global upload_form

    rf = requests.post(f"{srv_endpoint}/files", data=utils.json_bytes(file))

    assert rf.status_code == 201

    json_rf = json.loads(rf.text)
    
    assert json_rf
    assert 'upload_form' in json_rf
    assert json_rf['ready'] == False 

    upload_form = json_rf['upload_form']


@pytest.mark.dependency(name="test_create_file")
def test_file_upload():
    postv4 = json.loads(upload_form.replace("'", "\"")) 

    with open(file_path, 'rb') as f:
        files = {'file': (file_name, f)}
        response = requests.post(
            postv4['url'],
            data=postv4['fields'],
            files=files,
            verify=True,
            allow_redirects=True
        )
    assert "Uploaded." in response.text
    assert response.status_code == 201


@pytest.mark.dependency(name="test_file_upload")
def test_file_readiness(srv_endpoint):
    file = requests.get(f"{srv_endpoint}/files/1")
    json_file = json.loads(file.text)

    assert file.status_code == 200
    assert json_file['ready'] == True
    assert json_file['upload_form'] == ""


@pytest.mark.dependency(name="test_file_upload")
def test_file_download(srv_endpoint, tmp_path):
    file = requests.get(f"{srv_endpoint}/files/download/1", allow_redirects=True, stream=True)

    assert file.status_code == 200

    tmp_file = tmp_path / 'dltest.h5ad' 

    with open(tmp_file, 'ba+') as f:
        f.write(file.content)

    assert filecmp.cmp(tmp_file, file_path)
