import json
import os
from typing import Callable, List, Optional, TypedDict, Union

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
    DeployableInstance,
    EngineAction,
    HubComponent,
    HubServer,
    Server,
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


class InvalidActionError(Exception): ...


class ImageError(Exception): ...


class ContainerExecutionError(Exception): ...


class Engine:
    """
    The engine is responsible for handling the execution of instances
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
        self._docker_network = self._get_or_create_network()
        self._add_containers_to_network()

    @property
    def handlers(self) -> dict[EngineActionType, Callable[[Component], None]]:
        return {
            EngineActionType.RUN: self.run,
            EngineActionType.STOP: self.stop,
            EngineActionType.RESTART: self.restart,
        }

    def _get_or_create_network(self) -> str:
        network_name = self._compute_node.id
        try:
            net = self._docker_client.networks.get(network_name)
        except docker.errors.NotFound:
            net = self._docker_client.networks.create(
                name=network_name, driver="bridge"
            )
        return net

    def _add_containers_to_network(self) -> None:
        containers = self._get_deployed_containers()
        for container in containers:
            if (
                self._docker_network.name
                not in container.attrs["NetworkSettings"]["Networks"]
            ):
                self._docker_network.connect(container)

    def _get_instance_restart_policy(
        self, instance: DeployableInstance
    ) -> Optional[dict]:
        if instance.deployment_restart_policy:
            return {
                "Name": self.RESTART_POLICY_MAP[
                    instance.deployment_restart_policy
                ],
                "MaximumRetryCount": 0,
            }
        return None

    def _get_mem_limit(self, instance: DeployableInstance) -> str:
        map_ = self.DEPLOYMENT_SIZE_MAP.get(instance.deployment_capacity, None)
        if map_:
            return map_["memory"]
        return None

    def _get_labels(self, instance: DeployableInstance) -> dict:
        deploy_label = instance.get_deploy_label()
        labels = {
            "AgentID": self._compute_node.id,
            deploy_label: instance.id,
            "StateHash": instance.to_hash(),
        }
        return labels

    def _download_image(
        self, hub_instance: Union[HubComponent, HubServer]
    ) -> bytes:
        logger.info(
            f"Starting image download for component: {hub_instance.name} {hub_instance.version}"
        )
        try:
            image_bytes = hub_instance.get_image_file()
        except Exception as e:
            # TODO: Maybe retry? or fail component?
            logger.error(e)
            raise ImageError(
                f"Failed to download image for component: {hub_instance.name}"
            )
        return image_bytes

    def _load_image(
        self,
        image_file: bytes,
        hub_instance_name: str,
        hub_instance_version: str,
    ) -> Image:
        try:
            with open(image_file, "rb") as fid:
                images = self._docker_client.images.load(fid)
            image = images[0]
        except Exception as exc:
            raise ImageError(
                f"Failed to load image for instance: {hub_instance_name} {hub_instance_version}"
            ) from exc
        return image

    def _get_command(self, instance: DeployableInstance) -> List[str]:
        if instance.instance_type == "component":
            return [
                "./main.py",
                f"--component-id={instance.id}",
            ]
        return None

    def _get_environment(self, instance: DeployableInstance) -> dict:
        env = {
            **self._component_environment,
            "LOG_LEVEL": instance.deployment_log_level,
            "PROCESS_TYPE": instance.instance_type,
        }
        if instance.instance_type == "component":
            env["COMPONENT_ID"] = instance.id
        elif instance.instance_type == "server":
            env["SPLIGHT_SERVER_ID"] = instance.id
            for env_var in instance.env_vars:
                env[env_var.name] = env_var.value
        return env

    def _get_ports(self, instance: DeployableInstance) -> dict:
        if instance.instance_type == "server":
            ports = {}
            for port in instance.ports:
                ports[f"{port.internal_port}/{port.protocol}"] = (
                    port.exposed_port
                )
            return ports
        return None

    def _run_container(
        self,
        name: str,
        image: Image,
        environment: dict,
        labels: dict,
        restart_policy: dict,
        mem_limit: str,
        command: Optional[List[str]] = None,
        ports: Optional[dict] = None,
    ) -> Container:
        # TODO: add port exposing and env vars for servers
        # TODO: add network
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
                remove=False,
                command=command,
                labels=labels,
                restart_policy=restart_policy,
                mem_limit=mem_limit,
                log_config=log_config,
                ports=ports,
                network=self._docker_network.name,
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
                f"Failed to run container for instance: {name}"
            )

    def run(self, instance: DeployableInstance):
        instance.deployment_status = ComponentDeploymentStatus.PENDING
        instance.update_status()

        hub_instance = instance.get_hub_instance()
        # Download image
        try:
            image_file = self._download_image(hub_instance)
            # Load image
            image = self._load_image(
                image_file=image_file,
                hub_instance_name=hub_instance.name,
                hub_instance_version=hub_instance.version,
            )
        except ImageError as e:
            os.remove(image_file)
            instance.deployment_status = ComponentDeploymentStatus.FAILED
            instance.update_status()
            logger.error(e)
            return
        else:
            os.remove(image_file)

        # Run container
        logger.info(
            f"Running container for {instance.instance_type}: {instance.id}"
        )
        self._run_container(
            image=image,
            name=instance.id,
            environment=self._get_environment(instance),
            labels=self._get_labels(instance),
            command=self._get_command(instance),
            restart_policy=self._get_instance_restart_policy(instance),
            mem_limit=self._get_mem_limit(instance),
            ports=self._get_ports(instance),
            # TODO: add cpu limit
        )

    def handle_action(self, action: EngineAction):
        handler = self.handlers.get(action.type)
        if not handler:
            raise InvalidActionError(f"Invalid action type: {action.type}")
        handler(action.instance)

    def stop(self, instance: DeployableInstance) -> None:
        containers = self._get_deployed_containers(instance)
        if not containers:
            return
        try:
            for container in containers:
                logger.info(
                    f"Stopping container for {instance.instance_type}: {instance.id}"
                )
                container.stop()
                container.remove()
            instance.deployment_status = ComponentDeploymentStatus.STOPPED
            instance.update_status()
        except Exception:
            raise ContainerExecutionError(
                f"Failed to stop container for {instance.instance_type}: {instance.id}"
            )

    def restart(self, instance: DeployableInstance) -> None:
        logger.info(f"Restarting instance: {instance.id}")
        self.stop(instance)
        self.run(instance)

    def _get_deployed_containers(
        self, instance: Optional[DeployableInstance] = None
    ) -> List[Container]:
        labels = [f"AgentID={self._compute_node.id}"]
        if instance:
            labels.append(f"{instance.get_deploy_label()}={instance.id}")
        containers = self._docker_client.containers.list(
            filters={"label": labels},
            all=True,
        )
        return containers

    def get_instance_hash(self, instance: DeployableInstance) -> str:
        containers = self._get_deployed_containers(instance)
        if not containers:
            return None
        return containers[0].labels["StateHash"]

    def stop_all(self) -> List[DeployableInstance]:
        """
        Stop all running instances and return the ids.
        """
        setopped_instances: List[DeployableInstance] = []
        deployed_containers = self._get_deployed_containers()
        for container in deployed_containers:
            instance_id = container.labels.get("ComponentID", None)
            if not instance_id:
                instance_id = container.labels.get("ServerID", None)
                instance = Server(id=instance_id)
            else:
                instance = Component(id=instance_id)
            try:
                self.stop(instance)
                setopped_instances.append(instance)
            except ContainerExecutionError:
                logger.warning(
                    f"Failed to stop {instance.instance_type}: {instance.name}. "
                    f"Skipping {instance.instance_type}..."
                )
        return setopped_instances
