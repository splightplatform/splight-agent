from docker.models.containers import Container
import time
from splight_agent.settings import settings
from splight_lib.restclient import SplightRestClient
from splight_lib.auth.token import SplightAuthToken
from furl import furl

class Singleton:
    def __new__(cls, *args, **kw):
        if not hasattr(cls, "_instance"):
            org = super(Singleton, cls)
            cls._instance = org.__new__(cls, *args, **kw)
        return cls._instance

class Exporter(Singleton):
    _containers = {}
    _prev_status = {}

    def __init__(self):
        self._base_url = furl(settings.SPLIGHT_PLATFORM_API_HOST)
        self._client = SplightRestClient()
        token = SplightAuthToken(
            access_key=settings.SPLIGHT_ACCESS_ID,
            secret_key=settings.SPLIGHT_SECRET_KEY,
        )
        self._client.update_headers(token.header)

    def _get_component_status(self, container: Container):
        print(f"Container {container.name} status: {container.status}")
        status_map = {
            'created': 'Pending',
            'restarting': 'Pending',
            'running': 'Running',
            'removing': 'Stopped',
            'paused': 'Unknown',
            # 'dead': 'Unknown',
        }
        if container.status == 'exited':
            if container.attrs['State']['ExitCode'] == 0:
                return 'Succeeded'
            else:
                return 'Failed'
        return status_map.get(container.status, 'Unknown')

    def _update_component_status(self, component_id: str, status: str):
        container = self._containers.get(component_id)
        if not container:
            return None
        print(f"Component {component_id} status: {status}")
        response = self._client.patch(
            self._base_url / f"v2/engine/component/components/{component_id}/",
            data={"deployment_status": status},
        )
        return status

    def add_container(self, component_id, container):
        self._containers[component_id] = container
        print(f"Container {component_id} added")

    def get_container(self, component_id):
        return self._containers.get(component_id)

    def remove_container(self, component_id):
        container = self._containers.get(component_id)
        if container:
            container.stop()
            self._update_component_status(component_id, 'Stopped')
            # container.remove()
            self._containers.pop(component_id, None)
            self._prev_status.pop(component_id, None)
            print(f"Container {component_id} removed")


    def _monitor_containers(self):
        for component_id, container in self._containers.items():
            container.reload()
            status = self._get_component_status(container)
            if component_id not in self._prev_status or self._prev_status[component_id] != status:
                status = self._update_component_status(component_id, status)
                self._prev_status[component_id] = status
                print(f"Component {component_id} status updated: {status}")

    def start(self):
        print("Exporter started")
        while True:
            self._monitor_containers()
            time.sleep(10)


