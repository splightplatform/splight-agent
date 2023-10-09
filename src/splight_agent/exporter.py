from threading import Thread
from typing import Optional, Tuple

from docker import from_env

from splight_agent.logging import SplightLogger
from splight_agent.models import (
    Component,
    ComponentDeploymentStatus,
    ComputeNode,
    ContainerEventAction,
    partial,
)

logger = SplightLogger()


class Exporter:
    """
    The exporter is responsible for notifying the platform about the deployment status of components
    """

    def __init__(self, compute_node: ComputeNode) -> None:
        self._compute_node = compute_node
        self._client = from_env()
        self._thread = Thread(target=self._run_event_loop, daemon=True)
        self._transition_map = {
            ContainerEventAction.CREATE: lambda event: ComponentDeploymentStatus.PENDING,
            ContainerEventAction.START: lambda event: ComponentDeploymentStatus.RUNNING,
            ContainerEventAction.STOP: self._process_stop_event,
            ContainerEventAction.DIE: self._process_die_event,
        }
        self._stopped_containers = set()

    @property
    def _filters(self) -> dict:
        return {
            "label": [
                f"AgentID={self._compute_node.id}",
                "ComponentID",
                "Legacy",
            ],
            "event": [a.value for a in ContainerEventAction],
        }

    def _parse_event(
        self, event: dict
    ) -> Tuple[str, ComponentDeploymentStatus]:
        action = ContainerEventAction(event["Action"])
        component_id: str = event["Actor"]["Attributes"]["ComponentID"]
        deployment_status = self._transition_map[action](event)
        logger.info(
            f"Received event for component {component_id}: {action} -> {deployment_status}"
        )
        return component_id, deployment_status

    def _process_stop_event(self, event: dict) -> None:
        container_id = event["Actor"]["ID"]
        self._stopped_containers.add(container_id)
        return ComponentDeploymentStatus.STOPPED

    def _process_die_event(self, event: dict) -> None:
        container_id = event["Actor"]["ID"]
        if container_id in self._stopped_containers:
            self._stopped_containers.remove(container_id)
            raise ValueError("Container was stopped")
        exit_code = event["Actor"]["Attributes"].get("exitCode", None)
        logger.info(f"Container {container_id} exited with code {exit_code}")
        if exit_code and exit_code == "0":
            return ComponentDeploymentStatus.SUCCEEDED
        return ComponentDeploymentStatus.FAILED

    def _get_component_from_event(self, event: dict) -> Optional[Component]:
        """
        Returns a partial Component object or None if the event is not parsable
        """
        try:
            component_id, deployment_status = self._parse_event(event)
        except (KeyError, ValueError) as e:
            logger.warning(f"Could not parse event: {e}")
            return None
        return partial(Component)(
            id=component_id,
            deployment_status=deployment_status,
        )

    def _run_event_loop(self) -> None:
        for event in self._client.events(decode=True, filters=self._filters):
            component = self._get_component_from_event(event)
            if component:
                component.update_status()

    def start(self) -> None:
        """
        Launch the exporter daemon thread
        """
        self._thread.start()
        logger.info("Exporter started")

    def stop(self) -> None:
        """
        Stop the exporter daemon thread
        TODO: find a proper way to stop the thread
        """
        logger.info("Exporter stopped")
