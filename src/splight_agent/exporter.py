from docker.models.containers import Container
import time
from splight_agent.models import Component
from splight_agent.settings import settings

class Singleton:
    def __new__(cls, *args, **kw):
        if not hasattr(cls, "_instance"):
            org = super(Singleton, cls)
            cls._instance = org.__new__(cls, *args, **kw)
        return cls._instance

class Exporter(Singleton):
    _running_components = {}

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
    
    def add_container(self, component: Component, container: Container):
        self._running_components[component.id] = {
            'component': component,
            'container': container,
        }
        print(f"Container {component.name} added")

    def get_container(self, component_id):
        data = self._running_components.get(component_id, None)
        if data:
            return data['container']
        return None

    def get_component(self, component_id):
        data = self._running_components.get(component_id, None)
        if data:
            return data['component']
        return None

    def remove_container(self, component_id):
        data = self._running_components.get(component_id)
        if data:
            container = data['container']
            component = data['component']
            container.stop()
            component.update_status('Stopped')
            # container.remove()
            self._running_components.pop(component_id, None)
            print(f"Container {component_id} removed")


    def _monitor_containers(self):
        for component_id, data in self._running_components.items():
            container = data['container']
            container.reload()
            status = self._get_component_status(container)
            component: Component = data['component']
            if component.deployment_status != status:
                component.update_status(status)
                self._running_components[component_id]['component'] = component
                print(f"Component {component_id} status updated: {status}")

    def start(self):
        print("Exporter started")
        while True:
            self._monitor_containers()
            time.sleep(10)


