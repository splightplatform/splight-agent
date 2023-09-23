import json
from typing import Callable, List, Optional, TypedDict

import docker
from docker.models.containers import Image

from splight_agent.logging import SplightLogger
from splight_agent.models import (
    Component,
    ComputeNode,
    HubComponent,
    EngineAction,
    DeployedComponent,
)
from splight_agent.constants import DeploymentRestartPolicy, EngineActionType

logger = SplightLogger()


class ComponentEnvironment(TypedDict):
    """
    Environment variables to be passed to the component container
    """

    NAMESPACE: str
    SPLIGHT_ACCESS_ID: str
    SPLIGHT_SECRET_KEY: str
    SPLIGHT_PLATFORM_API_HOST: str
    SPLIGHT_GRPC_HOST: str


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

    RESTART_POLICY_MAP = {
        DeploymentRestartPolicy.ALWAYS: "always",
        DeploymentRestartPolicy.ON_FAILURE: "on-failure",
        DeploymentRestartPolicy.NEVER: "no",
    }

    def __init__(
        self,
        compute_node: ComputeNode,
        workspace_name: str,
        ecr_repository: str,
        componenent_environment: ComponentEnvironment,
    ) -> None:
        self._compute_node = compute_node
        self._workspace_name = workspace_name
        self._ecr_repository = ecr_repository
        self._component_environment = componenent_environment
        self._docker_client = docker.from_env()

    @property
    def handlers(self) -> dict[EngineActionType, Callable[[Component], None]]:
        return {
            EngineActionType.RUN: self.run,
            EngineActionType.STOP: self.stop,
            EngineActionType.RESTART: self.restart,
        }

    def _download_image(self, hub_component: HubComponent) -> bytes:
        logger.info(
            f"Starting image download for component: {hub_component.name}"
        )
        try:
            image_file = hub_component.get_image_file()
        except Exception as e:
            # TODO: Maybe retry?
            logger.error(e)
            raise ImageError(
                f"Failed to download image for component: {hub_component.name}"
            )
        return image_file

    def _load_image(
        self,
        image_file: bytes,
        hub_component_name: str,
        hub_component_version: str,
    ) -> Image:
        component_tag = f"{hub_component_name.lower()}-{self._workspace_name}-{hub_component_version}"
        try:
            self._docker_client.images.load(image_file)
            image = self._docker_client.images.get(
                f"{self._ecr_repository}:{component_tag}"
            )
        except Exception:
            raise ImageError(
                f"Failed to load image for component: {hub_component_name}"
            )
        return image

    def _run_container(
        self,
        image: Image,
        environment: dict,
        runspec: dict,
        labels: dict,
        restart_policy: dict,
    ) -> None:
        try:
            _ = self._docker_client.containers.run(
                image,
                detach=True,
                environment=environment,
                network_mode="host",  # TODO: delete after testing
                remove=False,
                command=["python", "runner.py", "-r", json.dumps(runspec)],
                labels=labels,
                restart_policy=restart_policy,
            )
        except Exception:
            raise ContainerExecutionError(
                f"Failed to run container for component: {runspec['name']}"
            )

    def run(self, component: Component):
        # Download image
        image_file = self._download_image(component.hub_component)

        # Load image
        image = self._load_image(
            image_file=image_file,
            hub_component_name=component.hub_component.name,
            hub_component_version=component.hub_component.version,
        )

        # Run container
        logger.info(f"Running container for component: {component.id}")
        self._run_container(
            image=image,
            environment={
                **self._component_environment,
                "LOG_LEVEL": component.deployment_log_level,
                "COMPONENT_ID": component.id,
            },
            labels={
                "AgentID": self._compute_node.id,
                "ComponentID": component.id,
                "DeploymentHash": component.get_deployment_hash(),
                "ComponentDeploymentStatus": component.deployment_status,
            },
            runspec={
                "name": component.hub_component.name,
                "version": component.hub_component.version,
                "input": component.input,
            },
            restart_policy={
                "Name": self.RESTART_POLICY_MAP.get(
                    component.deployment_restart_policy, "no"
                )
            },
            # TODO: add cpu and memory limit
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
            logger.info(f"Stopping container for component: {component.id}")
            deployed_component.container.stop()
            deployed_component.container.remove()
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
        container = self._docker_client.containers.list(
            filters={
                "label": [
                    f"AgentID={self._compute_node.id}",
                    f"ComponentID={component_id}",
                ]
            }
        )
        if container:
            return DeployedComponent(
                container=container[0],
                component_id=component_id,
                deployment_hash=container[0].labels["DeploymentHash"],
            )
        return None

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
