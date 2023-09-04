import json
import queue
from functools import cached_property
from threading import Thread
from typing import Dict, List, Optional, Callable

import docker
from docker.models.containers import Container
from pydantic import BaseModel
from enum import Enum

from splight_agent.logging import get_logger
from splight_agent.models import Component, HubComponent
from splight_agent.settings import settings

logger = get_logger()


class EngineAction(BaseModel):
    class ActionType(str, Enum):
        RUN = "run"
        STOP = "stop"
        RESTART = "restart"

    type: ActionType
    component: Component


class DeployedComponent(Component):
    container: Optional[Container]

    class Config:
        arbitrary_types_allowed = True


class InvalidActionError(Exception):
    ...


class Engine:
    """
    The engine is responsible for handling the execution of components
    """

    def __init__(self) -> None:
        self._deployed_components: dict[str, DeployedComponent] = {}

    @property
    def handlers(self) -> dict[EngineAction.ActionType, Callable[[Component], None]]:
        return {
            EngineAction.ActionType.RUN: self.run,
            EngineAction.ActionType.STOP: self.stop,
            EngineAction.ActionType.RESTART: self.stop,
        }

    @cached_property
    def _thread(self) -> Thread:
        return Thread(target=self._handle_actions, daemon=True)

    def handle_action(self, action: EngineAction):
        handler = self.handlers.get(action.type)
        if not handler:
            raise InvalidActionError(f"Invalid action type: {action.type}")
        handler(action.component)

    def _handle_actions(self):
        while True:
            action = self._actions_queue.get()
            self.handle_action(action)

    def start(self):
        """
        Launch the engine daemon thread
        """
        self._thread.start()

    def enqueue_action(self, action: EngineAction) -> None:
        self._actions_queue.put(action)

    @cached_property
    def _docker_client(self) -> docker.DockerClient:
        return docker.from_env()

    def _get_component_tag(self, hub_component: HubComponent):
        name = hub_component.name.lower()
        return f"{name}-{settings.WORKSPACE_NAME}-{hub_component.version}"

    def get_deployed_component(self, component_id: str) -> Optional[DeployedComponent]:
        return self._deployed_components.get(component_id)

    def run(self, component: Component):
        deployed_component = DeployedComponent(
            **component.dict(), container=None
        )
        self._deployed_components[component.id] = deployed_component

        component_tag = self._get_component_tag(component.hub_component)
        # pull docker image
        # TODO: Maybe add retry?
        try:
            image_file = component.hub_component.get_image_file()
        except Exception:
            logger.error(
                f"Failed to get image url for component {component.name}"
            )
            return

        self._docker_client.images.load(image_file)
        image = self._docker_client.images.get(
            f"{settings.ECR_REPOSITORY}:{component_tag}"
        )
        # run docker image
        run_spec = json.dumps(
            {
                "name": component.hub_component.name,
                "version": component.hub_component.version,
                "input": component.input,
            }
        )
        deployed_component.container = self._docker_client.containers.run(
            image,
            detach=True,
            environment={
                "NAMESPACE": settings.NAMESPACE,
                "SPLIGHT_ACCESS_ID": settings.SPLIGHT_ACCESS_ID,
                "SPLIGHT_SECRET_KEY": settings.SPLIGHT_SECRET_KEY,
                "SPLIGHT_PLATFORM_API_HOST": settings.SPLIGHT_PLATFORM_API_HOST,
                "SPLIGHT_GRPC_HOST": settings.SPLIGHT_GRPC_HOST,
                "LOG_LEVEL": "0",
                "COMPONENT_ID": component.id,
            },
            network_mode="host",  # TODO: delete after testing
            remove=False,
            command=["python", "runner.py", "-r", run_spec],
            labels={
                "AgentID": settings.COMPUTE_NODE_ID,
                "ComponentID": component.id,
                "StateHash": str(hash(json.dumps(component.input)))
            }
        )

    def stop(self, component: Component) -> None:
        deployed_component = self.get_deployed_component(component.id)
        if not deployed_component:
            return
        deployed_component.container.stop()
        deployed_component.container.remove()
        del self._deployed_components[component.id]
