import json
from enum import Enum
from typing import Callable, List, Optional

import docker
from docker.models.containers import Container
from pydantic import BaseModel

from splight_agent.logging import SplightLogger
from splight_agent.models import Component, HubComponent
from splight_agent.settings import settings

logger = SplightLogger()


class EngineActionType(str, Enum):
    RUN = "run"
    STOP = "stop"
    RESTART = "restart"


class EngineAction(BaseModel):
    type: EngineActionType
    component: Component


class DeployedComponent(Component):
    container: Optional[Container]

    class Config:
        arbitrary_types_allowed = True


class InvalidActionError(Exception):
    ...


class ImageError(Exception):
    ...


class ContainerExecutionError(Exception):
    ...


class Engine:
    """
    The engine is responsible for handling the execution of components
    """

    def __init__(self) -> None:
        self._deployed_components: dict[str, DeployedComponent] = {}
        self._docker_client = docker.from_env()

    @property
    def handlers(self) -> dict[EngineActionType, Callable[[Component], None]]:
        return {
            EngineActionType.RUN: self.run,
            EngineActionType.STOP: self.stop,
            EngineActionType.RESTART: self.restart,
        }

    def handle_action(self, action: EngineAction):
        handler = self.handlers.get(action.type)
        if not handler:
            raise InvalidActionError(f"Invalid action type: {action.type}")
        handler(action.component)

    def _get_component_tag(self, hub_component: HubComponent):
        name = hub_component.name.lower()
        return f"{name}-{settings.WORKSPACE_NAME}-{hub_component.version}"

    def get_deployed_component(
        self, component_id: str
    ) -> Optional[DeployedComponent]:
        return self._deployed_components.get(component_id)

    def run(self, component: Component):
        deployed_component = DeployedComponent(
            **component.dict(), container=None
        )
        self._deployed_components[component.id] = deployed_component

        component_tag = self._get_component_tag(component.hub_component)
        # # pull docker image
        # # TODO: Maybe add retry?
        # try:
        #     image_file = component.hub_component.get_image_file()
        # except Exception:
        #     raise ImageError(
        #         f"Failed to download image for component: {component.name}"
        #     )
        try:
            # self._docker_client.images.load(image_file)
            image = self._docker_client.images.get(
                # f"{settings.ECR_REPOSITORY}:{component_tag}"
                "609067598877.dkr.ecr.us-east-1.amazonaws.com/splight-components:random-integration-2.1.0"
            )
        except Exception:
            raise ImageError(
                f"Failed to load image for component: {component.name}"
            )
        # run docker container
        try:
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
                    "StateHash": str(hash(json.dumps(component.input))),
                },
            )
        except Exception:
            raise ContainerExecutionError(
                f"Failed to run container for component: {component.name}"
            )

    def stop(self, component: Component) -> None:
        deployed_component = self.get_deployed_component(component.id)
        if not deployed_component:
            return
        try:
            deployed_component.container.stop()
            deployed_component.container.remove()
            del self._deployed_components[component.id]
        except Exception:
            raise ContainerExecutionError(
                f"Failed to stop container for component: {component.name}"
            )

    def restart(self, component: Component) -> None:
        logger.info(f"Restarting component: {component.name}")
        self.stop(component)
        self.run(component)

    def stop_all(self) -> List[Component]:
        """
        Stops all running components and returns the ids of the stopped components.
        """
        stopped_components: List[Component] = []
        deployed_components = self._deployed_components.copy()
        for component in deployed_components.values():
            try:
                self.stop(component)
                stopped_components.append(component)
            except ContainerExecutionError:
                logger.warning(
                    f"Failed to stop component: {component.name}. "
                    f"Skipping component..."
                )
        return stopped_components
