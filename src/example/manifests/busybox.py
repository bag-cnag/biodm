from typing import Dict


def busybox() -> Dict[str, str]:
    """
    description: Deploys busybox and tie it to the user
    parameters:
        - in: path
          id: busybox
        - in: header
          X-User-Token: user token
    """
    return {'0': '1'}
