from typing import Dict, Type
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from biodm import config
from biodm.components import K8sManifest, Base

from entities import tables


## Cellxgene config
CXG_APP_NAME = 'cellxgene'
CXG_IMAGE = 'cellxgene:1.1.2-python3.11-slim-bookworm'
AWS_CLI_IMAGE = 'aws_cli:xsmall'
CXG_PORT = 5005
SERVICE_PORT = 38005
OAUTH2_NAMESPACE = 'ingress-nginx'
OAUTH2_APP_NAME = 'oauth2-proxy'
OAUTH2_PORT = 8091
PROXY_BUFFER_SIZE = '64k'


class CellXGeneManifest(K8sManifest):
    table: Type[Base] = tables.Visualization
    namespace = "cellxgene"

    async def gen_manifest(
        self,
        vis: tables.Visualization,
        session: AsyncSession,
        **_
    ) -> Dict[str, str]:
        """Generate SingleUserInstance (CRD) manifest for a CellxGene instance visualizing a File.

        :param vis: Newly inserted visualization
        :type vis: tables.Visualization
        :param session: Session handle
        :type session: AsyncSession
        :return: manifest to submit
        :rtype: Dict[str, str]
        """
        # 1. Get vis.user.username
        username = vis.username_user

        # 2. Get vis.file.key
        file: tables.File = await vis.awaitable_attrs.file
        file_key = await file.svc.gen_key(file, session)

        # 3. Instance name: for now uuid4
        return self.cellxgene_manifest(f"{CXG_APP_NAME}-{str(uuid4())}", username, file_key)

    def cellxgene_manifest(self, instance_name: str, user_id: str, file_key: str):
        """
        Return the SingleUserInstance manifest combining the deployment, service 
        and ingress with an extra field for the lifespan.
        """
        deployment, service, ingress = self._cellxgene_manifests(instance_name, user_id, file_key)

        return {
            "apiVersion": "cnag.eu/v1",
            "kind": "SingleUserInstance",
            "metadata": {
                "name": instance_name,
                "labels": {
                    "app": CXG_APP_NAME,
                    "instance": instance_name,
                    "user": user_id,
                }
            },
            "spec": {
                "lifespan": 999,
                "deployment": deployment,
                "service": service,
                "ingress": ingress
            }
        }

    def _cellxgene_manifests(self, name: str,  user_id: str, file_key: str):
        """
        Return the manifests needed to instanciate cellxgene as python dictionaries
        Sets the fields depending on variables
        """
        bucket_path = f"s3://{config.S3_BUCKET_NAME}"
        dataset = f"{bucket_path}/{file_key}"

        key_stem, key_ext = file_key.split('.', maxsplit=1)
        if key_ext != "h5ad":
            raise ValueError("Visualizer only supports h5ad files.")

        anno_files_path = f"{bucket_path}/cxg_on_k8/{key_stem}/{user_id}/"

        deployment = {
            "apiVersion":"apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": name,
                "labels": {
                    "app": CXG_APP_NAME,
                    "instance": name,
                    "user": user_id
                }
            },
            "spec": {
                "replicas": 1,
                "selector": {"matchLabels": {"app": CXG_APP_NAME}},
                "template": {
                    "metadata": {
                        "labels": {
                            "app": CXG_APP_NAME,
                            "instance": name,
                            "user": user_id
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
                                    f"aws s3 sync {anno_files_path} /data && "
                                    "touch /data/annotations.csv /data/gene_sets.csv"
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
                                dataset,
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
                                s3.upload('/data/annotations.csv', '{anno_files_path}'); \
                                s3.upload('/data/gene_sets.csv', '{anno_files_path}')"
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
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": name,
                "labels": {
                    "app": CXG_APP_NAME,
                    "instance": name,
                    "user": user_id
                },
            },
            "spec": {
                "ports": [{
                    "port": SERVICE_PORT,
                    "protocol": "TCP",
                    "targetPort": CXG_PORT
                }],
                "selector": {"instance": name},
                "type": "ClusterIP"
            }
        }
        ingress = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": name,
                "labels": {
                    "app": CXG_APP_NAME,
                    "instance": name,
                    "user": user_id
                },
                "annotations": {
                    "nginx.ingress.kubernetes.io/rewrite-target": "/$2",
                    "nginx.ingress.kubernetes.io/configuration-snippet": f"rewrite ^/{name}$ /{name}/ redirect;\n",
                    "nginx.ingress.kubernetes.io/auth-response-headers": "Authorization",
                    "nginx.ingress.kubernetes.io/auth-url": f"http://{OAUTH2_APP_NAME}.{OAUTH2_NAMESPACE}.svc.cluster.local:{OAUTH2_PORT}/oauth2/auth",
                    "nginx.ingress.kubernetes.io/auth-signin": f"https://{config.K8_HOST}/oauth2/sign_in?rd=$escaped_request_uri",
                    "nginx.ingress.kubernetes.io/proxy-buffer-size": PROXY_BUFFER_SIZE,
                },
            },
            "spec": {
                "ingressClassName": "nginx",
                "rules": [{
                    "host": config.K8_HOST,
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
