import json
import os
import pytest
from typing import Dict, Any, List
import requests

CHUNK_SIZE = 100*1024**2 # 100MB


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
    def rand_file(filename, size):
        """Generates a file of that size filling it with random values."""
        with open('%s'%filename, 'wb') as fout:
            fout.write(os.urandom(size))

    @staticmethod
    def multipart_upload(filepath, parts) -> List[Dict[str, str]]:
        parts_etags = []
        with open(filepath, 'rb') as file:
            for part in parts:
                assert 'form' in part

                part_data = file.read(CHUNK_SIZE)
                response = requests.put(
                    part['form'], data=part_data, headers={'Content-Encoding': 'gzip'}
                )
                assert response.status_code == 200

                # Get etag.
                etag = response.headers.get('ETag', "").replace('"', '') # comes with trailing quotes.
                assert etag

                parts_etags.append({'PartNumber': part['part_number'], 'ETag': etag})
        return parts_etags


@pytest.fixture
def utils():
    return Utils
