import time
from typing import Tuple, List, Any, Dict

from kubernetes import client
from biodm.component import ApiManager
from biodm.scope import Scope


class K8sManager(ApiManager):
    """Small util wrapper around kubernetes python client API.

    Related config:
        K8_HOST        Address of the kubernetes cluster.
        K8_TOKEN       Token of the authorized serviceaccount.
        K8_CERT        Path to kubernetes cluster root certificate
        K8_NAMESPACE   Active namespace

    The client exposes several APIs:
    - https://github.com/kubernetes-client/python/blob/a6d44ff625b5e8d8ad380a70245d40fa3d5472b2/kubernetes/README.md?plain=1
    Each api has access to a subset of the ressources.
    """
    # APIs
    _AppsV1Api: client.AppsV1Api = None
    _CoreV1Api: client.CoreV1Api = None
    _NetworkingV1Api: client.NetworkingApi = None
    _CustomObjectsApi: client.CustomObjectsApi = None

    def __init__(
        self,
        app,
        ip,
        port,
        host,
        cert,
        token,
        namespace,
    ) -> None:
        super().__init__(app=app)
        self._config = client.Configuration()
        self.host = host
        self.namespace = namespace
        self.authenticate(token, f"https://{ip}:{port}", cert)
        self._client = client.ApiClient(self._config)

    def authenticate(self, token, host, cert):
        """Set configuration with the credentials and certificate"""
        self._config.api_key["authorization"] = token
        self._config.api_key_prefix['authorization'] = 'Bearer'
        self._config.host = host
        self._config.ssl_ca_cert = cert

    @property
    def endpoint(self):
        return self._config.host

    def log(self, *args):
        """Conditional print"""
        if Scope.DEBUG in self.app.scope:
            self.logger.debug(*args)

    def change_namespace(self, namespace: str):
        """Change active namespace"""
        self.namespace = namespace

    @property
    def AppsV1Api(self) -> client.AppsV1Api:
        """AppsV1 kubernetes api"""
        if not self._AppsV1Api:
            self._AppsV1Api = client.AppsV1Api(self._client)
        return self._AppsV1Api

    @property
    def CoreV1Api(self) -> client.CoreV1Api:
        """CoreV1 kubernetes api"""
        if not self._CoreV1Api:
            self._CoreV1Api = client.CoreV1Api(self._client)
        return self._CoreV1Api

    @property
    def NetworkingV1Api(self) -> client.NetworkingV1Api:
        """NetworkingV1 kubernetes api"""
        if not self._NetworkingV1Api:
            self._NetworkingV1Api = client.NetworkingV1Api(self._client)
        return self._NetworkingV1Api

    @property
    def CustomObjectsApi(self) -> client.CustomObjectsApi:
        """NetworkingV1 kubernetes api"""
        if not self._CustomObjectsApi:
            self._CustomObjectsApi = client.CustomObjectsApi(self._client)
        return self._CustomObjectsApi

    def read_deployment(self, name: str, **kwargs) -> list:
        return self.AppsV1Api.read_namespaced_deployment(
            name=name, namespace=self.namespace, **kwargs
        )

    def list_pods(self):
        """List all pods."""
        self.log("Listing pods with their IPs:")
        ret = self.AppsV1Api.list_pod_for_all_namespaces(watch=False)
        for i in ret.items:
            self.log("%s\t%s\t%s" % (i.status.pod_ip, i.metadata.namespace, i.metadata.name))

    def list_deployments(self) -> list:
        """List all deployments."""
        ret = self.AppsV1Api.list_deployment_for_all_namespaces(watch=False)
        return [i for i in ret.items]

    def list_services_ports(self, **kwargs) -> list:
        """List all service ports in use, support selectors."""
        resp = self.CoreV1Api.list_service_for_all_namespaces(watch=False, **kwargs)
        ret = []
        for srv in resp.items:
            for port in srv.spec.ports:
                ret.append(port.port)
        return ret

    @staticmethod
    def get_name_in_manifest(manifest: Dict[str, str]) -> str:
        """Try to find and return metadata.name field from a manifest"""
        metadata = manifest.get("metadata", None)
        kind = manifest.get("kind", "ressource")
        if metadata:
            return metadata.get("name", None)
        raise Exception(f"field metadata.name required in {kind} manifest")

    def create_deployment(self, manifest: Dict[str, str]) -> None:
        """Create a deployment"""
        resp = None
        name = self.get_name_in_manifest(manifest)
        specs = manifest.get("spec", {})
        nreplicas = specs.get("replicas", 1)

        resp = self.AppsV1Api.create_namespaced_deployment(
            body=manifest,
            namespace=self.namespace
        )

        # Waiting for the instance to be up
        while True:
            resp = self.AppsV1Api.read_namespaced_deployment(
                name=name,
                namespace=self.namespace
            )
            if resp.status.available_replicas != nreplicas:
                break
            time.sleep(1)

        self.log(f"Deployment {name} up.")

    @staticmethod
    def get_custom_resource_params(manifest: Dict[str, str]) -> Tuple[str, str, str]:
        group, version = manifest['apiVersion'].split('/')
        plural = str(manifest['kind']).lower() + 's'
        return group, version, plural

    def create_custom_resource(self, manifest: Dict[str, str]) -> None:
        """Create a custom resource."""
        name = self.get_name_in_manifest(manifest)
        group, version, plural = self.get_custom_resource_params(manifest)

        resp = self.CustomObjectsApi.create_namespaced_custom_object(
            body=manifest,
            group=group,
            version=version,
            plural=plural,
            namespace=self.namespace
        )
        self.log(f"Response: {resp}")
        self.log(f"Custom object {manifest['kind']} with name: {name} up.")

    def read_ingress(self, name: str) -> None:
        return self.NetworkingV1Api.read_namespaced_ingress(
            name=name,
            namespace=self.namespace
        )

    def list_custom_object(self, manifest: Dict[str, str], label_selector) -> List[Any]:
        group, version, plural = self.get_custom_resource_params(manifest)
        return self.CustomObjectsApi.list_namespaced_custom_object(
            group=group,
            version=version,
            plural=plural,
            namespace=self.namespace,
            label_selector=label_selector
        )

    def delete_custom_object(
        self,
        name: str,
        manifest: Dict[str, str],
        group='cnag.eu',
        version='v1',
        plural='suis'
    ) -> Any:
        if manifest:
            group, version, plural = self.get_custom_resource_params(manifest)
        return self.CustomObjectsApi.delete_namespaced_custom_object(
            group=group,
            version=version,
            plural=plural,
            namespace=self.namespace,
            name=name)

    def create_service(self, manifest: Dict[str, str]):
        """Create a service"""
        name = self.get_name_in_manifest(manifest)
        resp = self.CoreV1Api.create_namespaced_service(
            body=manifest,
            namespace=self.namespace
        )
        time.sleep(1)
        self.log(f"Service {name} up - msg: {resp}.")

    def read_service_status(self, name: str):
        resp = self.CoreV1Api.read_namespaced_service_status(
            name=name,
            namespace=self.namespace
        )
        self.log(resp)

    def create_ingress(self, manifest: Dict[str, str]):
        """Create an ingress"""
        name = self.get_name_in_manifest(manifest)
        resp = self.NetworkingV1Api.create_namespaced_ingress(
            body=manifest,
            namespace=self.namespace
        )
        time.sleep(1)
        self.log(f"Ingress {name} setup.")
