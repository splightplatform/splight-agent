import time
from typing import List, Optional

from splight_agent.engine import Engine, EngineAction, EngineActionType
from splight_agent.logging import SplightLogger
from splight_agent.models import (
    Component,
    ComponentDeploymentStatus,
    ComputeNode,
)

logger = SplightLogger()


class Dispatcher:
    """
    The dispatcher is responsible for polling the API and dispatching actions to the engine
    in order to keep the state of the compute node in sync with the platform's state
    """

    def __init__(
        self,
        compute_node: ComputeNode,
        engine: Engine,
        poll_interval: int,
    ) -> None:
        self._poll_interval = poll_interval
        self._compute_node = compute_node
        self._engine = engine

    def _compute_action(self, component: Component) -> Optional[EngineAction]:
        deployed_component = self._engine.get_deployed_component(component.id)
        if component.deployment_active and not deployed_component:
            logger.info(f"Received RUN action for component {component.id}")
            return EngineAction(type=EngineActionType.RUN, component=component)
        elif (
            component.deployment_active
            and deployed_component
            and deployed_component != component
        ):
            logger.info(
                f"Received RESTART action for component {component.id}"
            )
            return EngineAction(
                type=EngineActionType.RESTART, component=component
            )
        elif not component.deployment_active and deployed_component:
            logger.info(f"Received STOP action for component {component.id}")
            return EngineAction(
                type=EngineActionType.STOP, component=component
            )
        return None

    def _compute_actions(self, components: list[Component]):
        return [
            action
            for component in components
            if (action := self._compute_action(component)) is not None
        ]

    def start(self):
        logger.info("Dispatcher started")
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
                logger.error(f"Failed to fetch components or compute actions: {e}")
            finally:
                time.sleep(self._poll_interval)

    def wait_for_components_to_stop(self, components: List[Component]):
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
            time.sleep(self._poll_interval)
