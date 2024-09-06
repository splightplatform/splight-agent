import hashlib
import json
import os
from abc import ABC, abstractmethod
from enum import Enum
from functools import cached_property
from typing import Any, Dict, List, Optional, Type, TypeVar

from docker.models.containers import Container
from pydantic import BaseModel

from splight_agent.constants import IMAGE_DIRECTORY, EngineActionType
from splight_agent.exceptions import DownloadError
from splight_agent.logging import SplightLogger
from splight_agent.rest_client import RestClient

logger = SplightLogger(__name__)


class APIObject(BaseModel):
    @cached_property
    def _rest_client(self) -> RestClient:
        return RestClient()


# Component
# (only the fields that are needed for the agent)
class HubComponent(APIObject):
    id: str
    name: str
    version: str
    splight_lib_version: Optional[str] = None
    splight_cli_version: Optional[str] = None

    @property
    def _image_link(self):
        params = {"type": "image"}
        response = self._rest_client.get(
            f"v2/hub/component/versions/{self.id}/download_url/",
            params=params,
        )
        response.raise_for_status()
        return response.json()["url"]

    def get_image_file(self):
        if not os.path.exists(IMAGE_DIRECTORY):
            os.makedirs(IMAGE_DIRECTORY)
        image_path = os.path.join(
            IMAGE_DIRECTORY, f"{self.name}-{self.version}"
        )
        try:
            image = self._rest_client.download(
                self._image_link, file_path=image_path
            )
        except Exception as exc:
            for file_name in os.listdir(IMAGE_DIRECTORY):
                os.remove(os.path.join(IMAGE_DIRECTORY, file_name))
            raise DownloadError("Unable to download docker image") from exc
        return image


class HubServer(APIObject):
    id: str
    name: str
    version: str

    @property
    def _image_link(self):
        params = {"type": "image"}
        response = self._rest_client.get(
            f"v2/hub/server/versions/{self.id}/download_url/",
            params=params,
        )
        response.raise_for_status()
        return response.json()["url"]

    def get_image_file(self):
        server_directory = os.path.join(IMAGE_DIRECTORY, "servers")
        if not os.path.exists(server_directory):
            os.makedirs(server_directory)
        image_path = os.path.join(
            server_directory, f"{self.name}-{self.version}"
        )
        try:
            image = self._rest_client.download(
                self._image_link, file_path=image_path
            )
        except Exception as exc:
            for file_name in os.listdir(server_directory):
                os.remove(os.path.join(server_directory, file_name))
            raise DownloadError("Unable to download docker image") from exc
        return image


class ContainerEventAction(str, Enum):
    CREATE = "create"
    START = "start"
    STOP = "stop"
    DIE = "die"


class ComponentDeploymentStatus(str, Enum):
    START_REQUESTED = "StartRequested"
    PENDING = "Pending"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    STOP_REQUESTED = "StopRequested"
    STOPPED = "Stopped"
    UNKNOWN = "Unknown"


class DeployableInstance(APIObject, ABC):
    _COMPARABLE_FIELDS = None
    _INSTANCE_URL = None

    id: str
    name: str
    deployment_active: bool
    deployment_status: ComponentDeploymentStatus
    deployment_capacity: str
    deployment_log_level: str
    deployment_restart_policy: str
    deployment_updated_at: Optional[str]
    compute_node: Optional[str]

    @property
    def instance_type(self):
        return self.__class__.__name__.lower()

    @abstractmethod
    def get_hub_instance(self):
        pass

    @abstractmethod
    def get_deploy_label(self):
        pass

    def __eq__(self, __value: object) -> bool:
        """only comparing attributes that are important for the deployment"""
        if not isinstance(__value, self.__class__):
            return NotImplemented

        if not self._COMPARABLE_FIELDS:
            raise NotImplementedError(
                "The class must define _COMPARABLE_FIELDS to compare instances"
            )

        return (
            all(
                getattr(self, field) == getattr(__value, field)
                for field in self._COMPARABLE_FIELDS
            )
            and self.deployment_active == __value.deployment_active
            and self.deployment_capacity == __value.deployment_capacity
            and self.deployment_log_level == __value.deployment_log_level
            and self.deployment_restart_policy
            == __value.deployment_restart_policy
        )

    def to_hash(self):
        data = self.dict()
        comparable_fields_dict = {
            field: data[field] for field in self._COMPARABLE_FIELDS
        }
        return hashlib.sha256(
            json.dumps(
                {
                    "deployment_capacity": self.deployment_capacity,
                    "deployment_log_level": self.deployment_log_level,
                    "deployment_restart_policy": self.deployment_restart_policy,
                    **comparable_fields_dict,
                }
            ).encode("utf-8")
        ).hexdigest()

    def update_status(self):
        if not self._INSTANCE_URL:
            raise NotImplementedError(
                "The class must define _INSTANCE_URL to update the status"
            )

        self._rest_client.post(
            f"{self._INSTANCE_URL}/{self.id}/update-status/",
            data={"deployment_status": self.deployment_status},
        )
        logger.info(
            f"{self.instance_type} {self.id} updated with status {self.deployment_status}"
        )

    def refresh(self):
        if not self._INSTANCE_URL:
            raise NotImplementedError(
                "The class must define _INSTANCE_URL to refresh the instance"
            )

        response = self._rest_client.get(f"{self._INSTANCE_URL}/{self.id}/")
        response.raise_for_status()
        data = response.json()
        for field in self.__fields__.values():
            if field.name in data:
                setattr(self, field.name, data[field.name])

    def __str__(self) -> str:
        return f"{self.instance_type}(id={self.id}, name={self.name}, deployment_active={self.deployment_active}))"


class Component(DeployableInstance):
    _COMPARABLE_FIELDS = ["input"]
    _INSTANCE_URL = "v2/engine/component/components"

    input: List[Dict[str, Any]]
    hub_component: HubComponent

    def get_hub_instance(self):
        return self.hub_component

    def get_deploy_label(self):
        return "ComponentID"


class Port(BaseModel):
    name: str
    protocol: str
    internal_port: int
    exposed_port: int


class EnvVar(BaseModel):
    name: str
    value: str


class Server(DeployableInstance):
    _COMPARABLE_FIELDS = ["config", "ports", "env_vars"]
    _INSTANCE_URL = "v2/engine/server/servers"

    config: List[Dict[str, Any]]
    ports: List[Port]
    env_vars: List[EnvVar]
    hub_server: HubServer

    def get_hub_instance(self):
        return self.hub_server

    def get_deploy_label(self):
        return "ServerID"


class ComputeNode(APIObject):
    id: str
    name: Optional[str]

    @property
    def components(self):
        response = self._rest_client.get(
            f"v2/engine/compute/nodes/all/{self.id}/components/",
        )
        return [Component(**c) for c in response.json()]

    @property
    def servers(self):
        response = self._rest_client.get(
            f"v2/engine/compute/nodes/all/{self.id}/servers/",
        )
        return [Server(**s) for s in response.json()]

    def report_version(self, version: str):
        response = self._rest_client.post(
            f"v2/engine/compute/nodes/all/{self.id}/update-version/",
            data={"agent_version": version},
        )
        return response


T = TypeVar("T", bound=BaseModel)


def partial(model: Type[T]) -> Type[T]:
    class OptionalModel(model):
        ...

    for field in OptionalModel.__fields__.values():
        field.required = False

    OptionalModel.__name__ = f"Optional{model.__name__}"

    return OptionalModel


class EngineAction(BaseModel):
    type: EngineActionType
    instance: DeployableInstance


class DeployedComponent(Component):
    container: Optional[Container]

    class Config:
        arbitrary_types_allowed = True


class ComputeNodeUsage(APIObject):
    compute_node: str
    timestamp: Optional[str]
    cpu_percent: float
    memory_percent: float

    def save(self):
        self._rest_client.post(
            f"v2/engine/compute/nodes/all/{self.compute_node}/usage/",
            data={
                "cpu_percent": self.cpu_percent,
                "memory_percent": self.memory_percent,
            },
        )
