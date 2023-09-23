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

    @property
    def _filters(self) -> dict:
        return {
            "label": [f"AgentID={self._compute_node.id}", "ComponentID"],
            "event": [a.value for a in ContainerEventAction],
        }

    def _parse_event(
        self, event: dict
    ) -> Tuple[str, ComponentDeploymentStatus]:
        action = ContainerEventAction(event["Action"])
        attributes = event["Actor"]["Attributes"]
        exit_code = attributes.get("exitCode", None)
        deployment_status_map = {
            ContainerEventAction.CREATE: ComponentDeploymentStatus.PENDING,
            ContainerEventAction.START: ComponentDeploymentStatus.RUNNING,
            ContainerEventAction.PAUSE: ComponentDeploymentStatus.UNKNOWN,
            ContainerEventAction.DIE: ComponentDeploymentStatus.STOPPED
            if exit_code and exit_code == "0"
            else ComponentDeploymentStatus.FAILED,
        }
        if action == ContainerEventAction.DIE:
            logger.info(f"Container died with exit code: {exit_code}")
            logger.info(event)
        deployment_status = deployment_status_map.get(action, None)
        if not deployment_status:
            raise ValueError(f"Invalid action: {action}")
        component_id: str = attributes["ComponentID"]
        return component_id, deployment_status

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
