import json
import os
from typing import Callable, List, Optional, TypedDict

import docker
from docker.models.containers import Container, Image
from pkg_resources import parse_version

from splight_agent.constants import (
    DeploymentRestartPolicy,
    DeploymentSize,
    EngineActionType,
)
from splight_agent.logging import SplightLogger
from splight_agent.models import (
    Component,
    ComponentDeploymentStatus,
    ComputeNode,
    EngineAction,
    HubComponent,
)
from splight_agent.settings import RUNNER_CLI_VERSION

logger = SplightLogger()


class ComponentEnvironment(TypedDict):
    """
    Environment variables to be passed to the component container
    """

    NAMESPACE: str
    SPLIGHT_ACCESS_ID: str
    SPLIGHT_SECRET_KEY: str
    SPLIGHT_PLATFORM_API_HOST: str


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

    DEPLOYMENT_SIZE_MAP = {
        DeploymentSize.SMALL: {"cpu": "0.5", "memory": "500m"},
        DeploymentSize.MEDIUM: {"cpu": "1", "memory": "3g"},
        DeploymentSize.LARGE: {"cpu": "3", "memory": "7g"},
        DeploymentSize.VERY_LARGE: {"cpu": "4", "memory": "16g"},
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

    def _get_component_restart_policy(
        self, component: Component
    ) -> Optional[dict]:
        if component.deployment_restart_policy:
            return {
                "Name": self.RESTART_POLICY_MAP[
                    component.deployment_restart_policy
                ],
                "MaximumRetryCount": 0,
            }
        return None

    def _get_mem_limit(self, component: Component) -> str:
        map_ = self.DEPLOYMENT_SIZE_MAP.get(
            component.deployment_capacity, None
        )
        if map_:
            return map_["memory"]
        return None

    def _get_labels(self, component: Component) -> dict:
        labels = {
            "AgentID": self._compute_node.id,
            "ComponentID": component.id,
            "StateHash": component.to_hash(),
        }
        return labels

    def _download_image(self, hub_component: HubComponent) -> bytes:
        logger.info(
            f"Starting image download for component: {hub_component.name} {hub_component.version}"
        )
        try:
            image_file = hub_component.get_image_file()
        except Exception as e:
            # TODO: Maybe retry? or fail component?
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
        try:
            with open(image_file, "rb") as fid:
                images = self._docker_client.images.load(fid)
            image = images[0]
        except Exception as exc:
            raise ImageError(
                f"Failed to load image for component: {hub_component_name}"
            ) from exc
        return image

    def _run_container(
        self,
        name: str,
        image: Image,
        environment: dict,
        labels: dict,
        command: List[str],
        restart_policy: dict,
        mem_limit: str,
    ) -> Container:
        log_config = {
            "type": "json-file",
            "config": {"max-size": "10m", "max-file": "3"},
        }
        try:
            self._docker_client.containers.run(
                image,
                name=name,
                detach=True,
                environment=environment,
                network_mode="host",  # TODO: delete after testing
                remove=False,
                command=command,
                labels=labels,
                restart_policy=restart_policy,
                mem_limit=mem_limit,
                log_config=log_config,
                healthcheck={
                    "test": [
                        "CMD",
                        "sh",
                        "-c",
                        "ls",
                        "/tmp/",
                        "|",
                        "grep",
                        "-q",
                        "healthy_",
                    ],
                    "interval": 5000000000,  # 5 seconds in nanoseconds
                    "timeout": 5000000000,  # 5 seconds in nanoseconds
                    "start_period": 60000000000,  # 60 seconds in nanoseconds
                },
            )
        except Exception:
            raise ContainerExecutionError(
                f"Failed to run container for component: {labels['ComponentID']}"
            )

    def run(self, component: Component):
        component.deployment_status = ComponentDeploymentStatus.PENDING
        component.update_status()

        # Download image
        try:
            image_file = self._download_image(component.hub_component)

            # Load image
            image = self._load_image(
                image_file=image_file,
                hub_component_name=component.hub_component.name,
                hub_component_version=component.hub_component.version,
            )
        except ImageError as e:
            import traceback, sys
            traceback.print_exc(file=sys.stdout)
            __import__('ipdb').set_trace()
            os.remove(image_file)
            component.deployment_status = ComponentDeploymentStatus.FAILED
            component.update_status()
            logger.error(e)
            return
        else:
            os.remove(image_file)

        # TODO: temporary fix for new runner
        labels = self._get_labels(component)
        cli_version = (
            parse_version(component.hub_component.splight_cli_version)
            if component.hub_component.splight_cli_version
            else None
        )
        is_legacy = (
            cli_version is not None
            and cli_version.release < RUNNER_CLI_VERSION.release
        )
        if is_legacy:
            labels["Legacy"] = "true"
            run_spec = {
                "name": component.hub_component.name,
                "version": component.hub_component.version,
                "input": component.input,
            }
            command = ["python", "runner.py", "-r", json.dumps(run_spec)]
        else:
            command = [
                "./main.py",
                f"--component-id={component.id}",
            ]

        # Run container
        logger.info(f"Running conatiner for component: {component.id}")
        self._run_container(
            image=image,
            name=component.id,
            environment={
                **self._component_environment,
                "LOG_LEVEL": component.deployment_log_level,
                "COMPONENT_ID": component.id,
                "PROCESS_TYPE": "component",
            },
            labels=labels,
            command=command,
            restart_policy=self._get_component_restart_policy(component),
            mem_limit=self._get_mem_limit(component),
            # TODO: add cpu limit
        )

    def handle_action(self, action: EngineAction):
        handler = self.handlers.get(action.type)
        if not handler:
            raise InvalidActionError(f"Invalid action type: {action.type}")
        handler(action.component)

    def stop(self, component: Component) -> None:
        containers = self._get_deployed_containers(component.id)
        if not containers:
            return
        try:
            for container in containers:
                logger.info(
                    f"Stopping container for component: {component.id}"
                )
                container.stop()
                container.remove()
            component.deployment_status = ComponentDeploymentStatus.STOPPED
            component.update_status()
        except Exception:
            raise ContainerExecutionError(
                f"Failed to stop container for component: {component.id}"
            )

    def restart(self, component: Component) -> None:
        logger.info(f"Restarting component: {component.id}")
        self.stop(component)
        self.run(component)

    def _get_deployed_containers(
        self, component_id: Optional[str] = None
    ) -> List[Container]:
        labels = [f"AgentID={self._compute_node.id}"]
        if component_id:
            labels.append(f"ComponentID={component_id}")
        containers = self._docker_client.containers.list(
            filters={"label": labels},
            all=True,
        )
        return containers

    def get_component_hash(self, component_id: str) -> str:
        containers = self._get_deployed_containers(component_id)
        if not containers:
            return None
        return containers[0].labels["StateHash"]

    def stop_all(self) -> List[Component]:
        """
        Stops all running components and returns the ids of the stopped components.
        """
        stopped_components: List[Component] = []
        deployed_containers = self._get_deployed_containers()
        for container in deployed_containers:
            component_id = container.labels["ComponentID"]
            component = Component(id=component_id)
            try:
                self.stop(component)
                stopped_components.append(component)
            except ContainerExecutionError:
                logger.warning(
                    f"Failed to stop component: {component.name}. "
                    f"Skipping component..."
                )
        return stopped_components
