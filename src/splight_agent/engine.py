import json
from enum import Enum
from typing import Callable, Optional, Protocol

import docker
from docker.models.containers import Container, Image
from pydantic import BaseModel

from splight_agent.logging import SplightLogger
from splight_agent.models import Component, ComputeNode, HubComponent

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


class EngineSettings(Protocol):

    @property
    def NAMESPACE(self) -> str:
        ...

    @property
    def SPLIGHT_ACCESS_ID(self) -> str:
        ...

    @property
    def SPLIGHT_SECRET_KEY(self) -> str:
        ...

    @property
    def SPLIGHT_PLATFORM_API_HOST(self) -> str:
        ...

    @property
    def SPLIGHT_GRPC_HOST(self) -> str:
        ...


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

    def __init__(self, compute_node: ComputeNode, settings: EngineSettings) -> None:
        self._compute_node = compute_node
        self._settings = settings
        self._deployed_components: dict[str, DeployedComponent] = {}
        self._docker_client = docker.from_env()

    @property
    def handlers(self) -> dict[EngineActionType, Callable[[Component], None]]:
        return {
            EngineActionType.RUN: self.run,
            EngineActionType.STOP: self.stop,
            EngineActionType.RESTART: self.restart,
        }

    def _get_component_tag(self, hub_component: HubComponent):
        name = hub_component.name.lower()
        return f"{name}-{self._settings.WORKSPACE_NAME}-{hub_component.version}"

    def _get_component_environment(self, component: Component) -> dict:
        return {
            "NAMESPACE": self._settings.NAMESPACE,
            "SPLIGHT_ACCESS_ID": self._settings.SPLIGHT_ACCESS_ID,
            "SPLIGHT_SECRET_KEY": self._settings.SPLIGHT_SECRET_KEY,
            "SPLIGHT_PLATFORM_API_HOST": self._settings.SPLIGHT_PLATFORM_API_HOST,
            "SPLIGHT_GRPC_HOST": self._settings.SPLIGHT_GRPC_HOST,
            "LOG_LEVEL": component.deployment_log_level,
            "COMPONENT_ID": component.id,
        }

    def _get_component_labels(self, component: Component) -> dict:
        return {
            "AgentID": self._compute_node.id,
            "ComponentID": component.id,
            "StateHash": str(hash(json.dumps(component.input))),
        }

    def _get_component_run_spec(self, component: Component) -> str:
        return json.dumps(
            {
                "name": component.hub_component.name,
                "version": component.hub_component.version,
                "input": component.input,
            }
        )

    def _download_image(self, hub_component: HubComponent) -> bytes:
        try:
            image_file = hub_component.get_image_file()
        except Exception:
            # TODO: Maybe retry?
            raise ImageError(
                f"Failed to download image for component: {hub_component.name}"
            )
        return image_file

    def _load_image(self, image_file: bytes, component_name: str, component_tag: str) -> Image:
        try:
            self._docker_client.images.load(image_file)
            image = self._docker_client.images.get(
                f"{self._settings.ECR_REPOSITORY}:{component_tag}"
            )
        except Exception:
            raise ImageError(
                f"Failed to load image for component: {component_name}"
            )
        return image

    def _run_container(
            self, environment: dict, labels: dict, run_spec: str, image: Image, component: Component
    ) -> Container:
        try:

            container = self._docker_client.containers.run(
                image,
                detach=True,
                environment=environment,
                network_mode="host",  # TODO: delete after testing
                remove=False,
                command=["python", "runner.py", "-r", run_spec],
                labels=labels,
            )
        except Exception:
            raise ContainerExecutionError(
                f"Failed to run container for component: {component.name}"
            )
        return container

    def run(self, component: Component):
        # Add component to deployed components
        deployed_component = DeployedComponent(**component.dict(), container=None)
        self._deployed_components[component.id] = deployed_component

        # Download image
        image_file = self._download_image(component.hub_component)

        # Load image
        image = self._load_image(
            image_file=image_file,
            component_name=component.name,
            component_tag=self._get_component_tag(component.hub_component)
        )

        # Run container
        deployed_component.container = self._run_container(
            environment=self._get_component_environment(component),
            labels=self._get_component_labels(component),
            run_spec=self._get_component_run_spec(component),
            image=image,
            component=component
        )

    def handle_action(self, action: EngineAction):
        handler = self.handlers.get(action.type)
        if not handler:
            raise InvalidActionError(f"Invalid action type: {action.type}")
        handler(action.component)

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

    def get_deployed_component(
        self, component_id: str
    ) -> Optional[DeployedComponent]:
        return self._deployed_components.get(component_id)
