import time
from typing import List, Optional

from splight_agent.engine import Engine, EngineAction, EngineActionType
from splight_agent.logging import SplightLogger
from splight_agent.models import (
    ComponentDeploymentStatus,
    ComputeNode,
    DeployableInstance,
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

    def _compute_action(self, instance: DeployableInstance) -> Optional[EngineAction]:
        instance_hash = self._engine.get_instance_hash(instance)
        if instance.deployment_active and not instance_hash:
            logger.info(f"Received RUN action {instance.instance_type} {instance.id}")
            return EngineAction(type=EngineActionType.RUN, instance=instance)
        elif (
            instance.deployment_active
            and instance_hash
            and instance_hash != instance.to_hash()
        ):
            logger.info(
                f"Received RESTART action {instance.instance_type} {instance.id}"
            )
            return EngineAction(
                type=EngineActionType.RESTART, instance=instance
            )
        elif not instance.deployment_active:
            if instance_hash:
                logger.info(
                    f"Received STOP action {instance.instance_type} {instance.id}"
                )
                return EngineAction(
                    type=EngineActionType.STOP, instance=instance
                )
            elif (
                instance.deployment_status
                != ComponentDeploymentStatus.STOPPED
            ):
                logger.info(
                    f"Instance {instance.id} has status {instance.deployment_status} and should be STOPPED. Setting status to STOPPED."
                )
                instance.deployment_status = ComponentDeploymentStatus.STOPPED
                instance.update_status()
                return None
        return None

    def _compute_actions(self) -> List[EngineAction]:
        instances = self._compute_node.components + self._compute_node.servers
        actions = [
            action
            for instance in instances
            if (action := self._compute_action(instance)) is not None
        ]
        return actions

    def start(self):
        logger.info("Dispatcher started")
        while True:
            try:
                actions = self._compute_actions()
                for action in actions:
                    try:
                        self._engine.handle_action(action)
                    except Exception as e:
                        logger.error(
                            f"The engine failed to handle action {action.type}:\n{e}\n Continuing..."
                        )
            except Exception as e:
                logger.error(
                    f"Failed to fetch instances or compute actions: {e}"
                )
            finally:
                time.sleep(self._poll_interval)

    def wait_for_instances_to_stop(self, instances: List[DeployableInstance]):
        while True:
            for index, instance in  enumerate(instances):
                instance.refresh()
                if (
                    instance.deployment_status
                    == ComponentDeploymentStatus.STOPPED
                ):
                    instances.pop(index)
            if not instances:
                break
            time.sleep(self._poll_interval)
