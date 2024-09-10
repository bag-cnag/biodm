import json
import os
import pytest
from typing import Dict, Any


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


@pytest.fixture
def utils():
    return Utils
