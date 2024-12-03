import json
import pytest
import requests
import filecmp
from pathlib import Path
from math import ceil
from typing import Dict, Any

from conftest import CHUNK_SIZE


project = {"name": "pr_test"}
dataset = {
    "name": "ds_test",
    "project_id": "1",
    "contact": {
        "username": "u_test"
    },
}


small_file_name = "small.bin"
small_file_path: Path
small_file_upload_form: Dict[str, str]
small_file = {}


big_file_name = "big.bin"
big_file_path: Path
big_file_upload_forms: Dict[str, Any]
big_file = {}


def test_create_project_dataset(srv_endpoint, utils):
    rpr = requests.post(f"{srv_endpoint}/projects", data=utils.json_bytes(project))
    rds = requests.post(f"{srv_endpoint}/datasets", data=utils.json_bytes(dataset))


    assert rpr.status_code == 201
    assert rds.status_code == 201


@pytest.mark.dependency(name="test_create_project_dataset")
def test_create_file(srv_endpoint, utils, tmpdir):
    global small_file_path, small_file_upload_form, small_file

    small_file_path = Path(tmpdir) / small_file_name
    utils.rand_file(small_file_path, ceil(0.5*CHUNK_SIZE)) # -> 1 chunk.

    small_file = {
        "filename": small_file_path.name.split('.')[0],
        "extension": small_file_path.name.split('.')[1],
        "size": small_file_path.stat().st_size,
        "dataset_id": "1",
        "dataset_version": "1",
    }
    response = requests.post(f"{srv_endpoint}/files", data=utils.json_bytes(small_file))

    assert response.status_code == 201

    json_rf = json.loads(response.text)

    assert json_rf
    assert 'upload' in json_rf
    assert json_rf['ready'] == False 
    assert 'id' in json_rf
    small_file['id'] = json_rf['id']

    upload = json_rf['upload']
    assert 'parts' in upload
    assert len(upload['parts']) == 1
    small_file_upload_form = upload['parts']


@pytest.mark.dependency(name="test_create_file")
def test_file_upload(srv_endpoint, utils):
    parts_etags = utils.multipart_upload(small_file_path, small_file_upload_form)
    # Send completion notice.
    complete = requests.put(
        f"{srv_endpoint}/files/{small_file['id']}/complete",
        data=utils.json_bytes(parts_etags)
    )
    assert complete.status_code == 201
    assert 'Completed.' in complete.text


def test_create_oversized_file(srv_endpoint, utils):
    small_file = {
        "filename": small_file_path.name.split('.')[0] + "_os1",
        "extension": small_file_path.name.split('.')[1],
        "size": 1000*1024**3, # 1000GB
        "dataset_id": "1",
        "dataset_version": "1",
    }
    response = requests.post(f"{srv_endpoint}/files", data=utils.json_bytes(small_file))

    assert response.status_code == 400
    assert "File exceeding 100 GB" in response.text


@pytest.mark.dependency(name="test_file_upload")
def test_file_readiness(srv_endpoint):
    response = requests.get(f"{srv_endpoint}/files/{small_file['id']}")

    assert response.status_code == 200

    json_file = json.loads(response.text)

    assert json_file['ready'] == True
    assert json_file['upload'] == None


@pytest.mark.dependency(name="test_file_upload")
def test_file_download(srv_endpoint, tmp_path):
    url_response = requests.get(
        f"{srv_endpoint}/files/{small_file['id']}/download"
    )

    assert url_response.status_code == 200

    file_response = requests.get(url_response.text, stream=True)

    tmp_file = tmp_path / 'dl_big.bin'

    assert file_response.status_code == 200

    tmp_file = tmp_path / 'dl_small.bin'

    with open(tmp_file, 'ba+') as f:
        f.write(file_response.content)

    assert filecmp.cmp(tmp_file, small_file_path)


@pytest.mark.dependency(name="test_file_download")
def test_file_dl_count(srv_endpoint):
    file = requests.get(f"{srv_endpoint}/files/{small_file['id']}?fields=dl_count")

    assert file.status_code == 200

    json_file = json.loads(file.text)
    assert json_file['dl_count'] == 1


@pytest.mark.dependency(name="test_create_project_dataset")
def test_create_large_file(srv_endpoint, utils, tmpdir):
    global big_file_path, big_file_upload_forms, big_file

    big_file_path = Path(tmpdir) / big_file_name
    utils.rand_file(big_file_path, ceil(2.5*CHUNK_SIZE)) # -> 3 chunks.

    big_file = {
        "filename": big_file_path.name.split('.')[0],
        "extension": big_file_path.name.split('.')[1],
        "size": big_file_path.stat().st_size,
        "dataset_id": "1",
        "dataset_version": "1",
    }

    rf = requests.post(f"{srv_endpoint}/files", data=utils.json_bytes(big_file))

    assert rf.status_code == 201

    json_rf = json.loads(rf.text)

    assert json_rf
    assert 'upload' in json_rf
    assert 'id' in json_rf
    big_file['id'] = json_rf['id']
    upload = json_rf['upload']

    assert 'parts' in upload
    big_file_upload_forms = upload['parts']
    assert len(big_file_upload_forms) == 3


@pytest.mark.dependency(name="test_create_large_file")
def test_upload_large_file(srv_endpoint, utils):
    global big_file, big_file_path, big_file_upload_forms

    parts_etags = utils.multipart_upload(big_file_path, big_file_upload_forms)

    # Send completion notice.
    complete = requests.put(
        f"{srv_endpoint}/files/{big_file['id']}/complete",
        data=utils.json_bytes(parts_etags)
    )
    assert complete.status_code == 201
    assert 'Completed.' in complete.text


@pytest.mark.dependency(name="test_upload_large_file")
def test_download_large_file(srv_endpoint, tmp_path):
    url_response = requests.get(
        f"{srv_endpoint}/files/{big_file['id']}/download"
    )

    assert url_response.status_code == 200

    file_response = requests.get(url_response.text, stream=True)

    tmp_file = tmp_path / 'dl_big.bin'

    assert file_response.status_code == 200

    with open(tmp_file, 'ba+') as f:
        f.write(file_response.content)

    assert filecmp.cmp(tmp_file, big_file_path)


@pytest.mark.dependency(name="test_upload_large_file")
def test_create_updload_and_complete_undersized_file(srv_endpoint, utils):
    big_file = {
        "filename": big_file_path.name.split('.')[0] + "_us2",
        "extension": big_file_path.name.split('.')[1],
        "size": big_file_path.stat().st_size + CHUNK_SIZE,
        "dataset_id": "1",
        "dataset_version": "1",
    }

    response = requests.post(f"{srv_endpoint}/files", data=utils.json_bytes(big_file))
    assert response.status_code == 201
    # Get form.
    json_rf = json.loads(response.text)
    upload = json_rf['upload']
    assert 'parts' in upload
    assert len(upload['parts']) == len(big_file_upload_forms) + 1
    # Upload
    parts_etags = utils.multipart_upload(small_file_path, upload['parts'])
    # Send completion notice.
    complete = requests.put(
        f"{srv_endpoint}/files/{json_rf['id']}/complete",
        data=utils.json_bytes(parts_etags)
    )
    assert complete.status_code == 400
    assert 'EntityTooSmall' in complete.text
