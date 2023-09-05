from functools import cached_property
from threading import Thread
from typing import Optional, Tuple

from docker import DockerClient, from_env

from splight_agent.logging import get_logger
from splight_agent.models import (
    Component,
    ComponentDeploymentStatus,
    ContainerEventAction,
    partial,
)
from splight_agent.settings import settings

logger = get_logger()


class Exporter:
    """
    The exporter is responsible for notifying the platform about the deployment status of components
    """

    def __init__(self) -> None:
        self._client = from_env()
        self._thread = Thread(target=self._run_event_loop, daemon=True)

    _TRANSITION_MAP = {
        ContainerEventAction.CREATE: ComponentDeploymentStatus.PENDING,
        ContainerEventAction.START: ComponentDeploymentStatus.RUNNING,
        ContainerEventAction.STOP: ComponentDeploymentStatus.STOPPED,
    }

    @property
    def _filters(self) -> dict:
        return {
            "label": [f"AgentID={settings.COMPUTE_NODE_ID}", "ComponentID"],
            "event": [a.value for a in ContainerEventAction],
        }

    def _parse_event(self, event: dict) -> Tuple[str, ContainerEventAction]:
        action = ContainerEventAction(event["Action"])
        component_id: str = event["Actor"]["Attributes"]["ComponentID"]
        return component_id, action

    def _get_component_from_event(self, event: dict) -> Optional[Component]:
        """
        Returns a partial Component object or None if the event is not parsable
        """
        try:
            component_id, action = self._parse_event(event)
            deployment_status = self._TRANSITION_MAP[action]
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
                component.update()

    def start(self) -> None:
        """
        Launch the exporter daemon thread
        """
        self._thread.start()
        logger.info("Exporter started")
