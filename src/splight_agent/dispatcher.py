import time
from typing import List, Optional

from splight_agent.engine import Engine, EngineAction, EngineActionType
from splight_agent.logging import SplightLogger
from splight_agent.models import (
    Component,
    ComponentDeploymentStatus,
    ComputeNode,
)
from splight_agent.settings import settings

logger = SplightLogger()


class Dispatcher:
    """
    The dispatcher is responsible for polling the API and dispatching actions to the engine
    in order to keep the state of the compute node in sync with the platform's state
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @property
    def _compute_node(self) -> ComputeNode:
        return ComputeNode(id=settings.COMPUTE_NODE_ID)

    def _execute_stop(self, component):
        container = self._exporter.get_container(component.id)
        if container:
            container.stop()
            self._exporter.remove_container(component.id)

    def _compute_action(self, component: Component) -> Optional[EngineAction]:
        deployed_component = self._engine.get_deployed_component(component.id)
        if component.deployment_active and not deployed_component:
            return EngineAction(type=EngineActionType.RUN, component=component)
        elif (
            component.deployment_active
            and deployed_component
            and deployed_component != component
        ):
            return EngineAction(
                type=EngineActionType.RESTART, component=component
            )
        elif not component.deployment_active and deployed_component:
            return EngineAction(
                type=EngineActionType.STOP, component=component
            )
        return None

    def _compute_actions(self, components: List[Component]):
        return [
            action
            for component in components
            if (action := self._compute_action(component)) is not None
        ]

    def start(self):
        while True:
            try:
                actions = self._compute_actions(self._compute_node.components)
                for action in actions:
                    try:
                        self._engine.handle_action(action)
                    except Exception as e:
                        logger.error(
                            f"The engine failed to handle action {action.type}:\n{e}\n Continuing..."
                        )
            except Exception as e:
                logger.error(f"Failed to compute actions: {e}")
            finally:
                time.sleep(settings.API_POLL_INTERVAL)

    def wait_for_components_to_stop(self, components: List[Component]):
        # TODO: how can we add a timeout here?
        while True:
            for index, component in enumerate(components):
                component.refresh()
                if (
                    component.deployment_status
                    == ComponentDeploymentStatus.STOPPED
                ):
                    components.pop(index)
            if not components:
                break
            time.sleep(settings.API_POLL_INTERVAL)
