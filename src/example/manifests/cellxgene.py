from typing import Dict
from example import config 


## Cellxgene config
CXG_APP_NAME = 'cellxgene'
CXG_IMAGE = 'cellxgene:xsmall'
AWS_CLI_IMAGE = 'aws_cli:xsmall'
CXG_PORT = 5005
SERVICE_PORT = 38005
NAMESPACE = "cellxgene"
PROXY_BUFFER_SIZE = '64k'
HOST_NAME = config.K8_HOST

# Or have another serviceaccount for this
OAUTH2_CLIENT_ID = config.CLIENT_ID
OAUTH2_CLIENT_SECRET = config.CLIENT_SECRET
OAUTH2_NAMESPACE = 'ingress-nginx'
OAUTH2_APP_NAME = 'oauth2-proxy'
OAUTH2_PORT = 8091


def cellxgene() -> Dict[str, str]:
    """
    description: Deploys cellxgene and tie it to the user
    parameters:
        - in: path
          id: busybox
        - in: header
          X-User-Token: user token
        - in: query
          dataset: s3 path to an .h5ad dataset
    """
    name = ""
    return cellxgene_manifest(name)


def cellxgene_manifest(name: str):
    """
    Return the SingleUserInstance manifest combining the deployment, service 
    and ingress with an extra field for the lifespan  
    """
    deployment, service, ingress = cellxgene_manifests(name)

    return {
        "apiVersion": "cnag.eu/v1",
        "kind": "SingleUserInstance",
        "metadata": {
            "name": name,
            "labels": {
                "app": CXG_APP_NAME,
                "instance": name
            }
        },
        "spec": {
            "lifespan": 999,
            "deployment": deployment,
            "service": service,
            "ingress": ingress
        }
    }

def cellxgene_manifests(name: str):
    """
    Return the manifests needed to instanciate cellxgene as python dictionaries
    Sets the fields depending on variables
    """
    USERNAME = "UserId"
    DATASETNAME = "DataSetId"
    DATASET = "https://github.com/chanzuckerberg/cellxgene/raw/main/example-dataset/pbmc3k.h5ad"
    BUCKET = "s3://bucketdevel3tropal"
    USER_FILES_DIR = "cxg_on_k8"
    USER_FILES_PATH = f'{BUCKET}/{USER_FILES_DIR}/{USERNAME}/{DATASETNAME}/'

    deployment = {
        "apiVersion":"apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": name,
            "labels": {
                "app": CXG_APP_NAME,
                "instance": name
            }
        },
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": {"app": CXG_APP_NAME}},
            "template": {
                "metadata": {
                    "labels": {
                        "app": CXG_APP_NAME,
                        "instance": name
                    }
                },
                "spec": {
                    "securityContext": {
                        "runAsUser": 1000,
                        "runAsGroup": 1000,
                        "fsGroup": 1000,
                    },
                    "initContainers": [{
                        "name": "init-cellxgene",
                        "image": AWS_CLI_IMAGE,
                        "command": [
                            "/bin/sh", "-c", (
                                f"aws s3 sync {USER_FILES_PATH} /data && "
                                f"touch /data/annotations.csv /data/gene_sets.csv"
                            )
                        ],
                        "envFrom": [{"secretRef": {"name": "aws-cred-secret"}}],
                        "volumeMounts": [{
                            "name": "data",
                            "mountPath": "/data"
                        }]
                    }],
                    "containers": [{
                        "name": name,
                        "image": CXG_IMAGE,
                        "ports": [{"containerPort": CXG_PORT}],
                        "args": [
                            "launch", "--verbose",
                            "-p", f"{CXG_PORT}",
                            "--host", "0.0.0.0",
                            DATASET,
                            "--annotations-file", "/data/annotations.csv",
                            "--gene-sets-file", "/data/gene_sets.csv"
                        ],
                        "envFrom": [{"secretRef": {"name": "aws-cred-secret"}}],
                        "volumeMounts": [{
                            "name": "data",
                            "mountPath": "/data"
                        }],
                        "lifecycle": { "preStop": { "exec": { "command": [
                            "/usr/local/bin/python", "-c",
                            f"from fsspec import filesystem as fs; s3 = fs('s3');    \
                            s3.upload('/data/annotations.csv', '{USER_FILES_PATH}'); \
                            s3.upload('/data/gene_sets.csv', '{USER_FILES_PATH}')"
                        ]}}},
                    }],
                    "volumes": [{
                        "name": "data",
                        "emptyDir": {}
                    }]
                }
            }
        }
    }
    service = {
        'apiVersion': 'v1',
        'kind': 'Service',
        'metadata': {
            'name': name,
            'labels': {
                'app': CXG_APP_NAME,
                'instance': name
            },
        },
        'spec': {
            'ports': [{
                'port': SERVICE_PORT,
                'protocol': 'TCP',
                'targetPort': CXG_PORT
            }],
            'selector': {'instance': name},
            'type': 'ClusterIP'
        }
    }
    ingress = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": {
            "name": name,
            "labels": {
                "app": CXG_APP_NAME,
                "instance": name
            },
            "annotations": {
                "nginx.ingress.kubernetes.io/rewrite-target": "/$2",
                "nginx.ingress.kubernetes.io/configuration-snippet": f"rewrite ^/{name}$ /{name}/ redirect;\n",
                "nginx.ingress.kubernetes.io/auth-response-headers": "Authorization",
                "nginx.ingress.kubernetes.io/auth-url": f"http://{OAUTH2_APP_NAME}.{OAUTH2_NAMESPACE}.svc.cluster.local:{OAUTH2_PORT}/oauth2/auth",
                "nginx.ingress.kubernetes.io/auth-signin": f"https://{HOST_NAME}/oauth2/sign_in?rd=$escaped_request_uri",
                "nginx.ingress.kubernetes.io/proxy-buffer-size": PROXY_BUFFER_SIZE,
            },
        },
        "spec": {
            "ingressClassName": "nginx",
            "rules": [{
                "host": HOST_NAME,
                "http": {
                    "paths": [{
                        "pathType": "ImplementationSpecific",
                        "path": f"/{name}(/|$)(.*)",
                        "backend": {
                            "service": {
                                "name": name,
                                "port": {"number": SERVICE_PORT}
                            }
                        }
                    }]
                }
            }]
        }
    }

    return deployment, service, ingress
