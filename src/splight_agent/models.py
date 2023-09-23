from enum import Enum
from functools import cached_property
from typing import Any, Dict, List, Optional, Type, TypeVar
import json
from docker.models.containers import Container

from pydantic import BaseModel
from splight_agent.constants import EngineActionType

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

    @property
    def _image_link(self):
        response = self._rest_client.post(
            "v2/hub/download/image_url/",
            data={"name": self.name, "version": self.version},
        )
        response.raise_for_status()
        return response.json()["url"]

    def get_image_file(self):
        return self._rest_client.download(self._image_link)


class ContainerEventAction(str, Enum):
    CREATE = "create"
    START = "start"
    DIE = "stop"
    PAUSE = "pause"


class ComponentDeploymentStatus(str, Enum):
    PENDING = "Pending"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    STOPPED = "Stopped"
    UNKNOWN = "Unknown"


class Component(APIObject):
    id: str
    name: str
    input: List[Dict[str, Any]]
    hub_component: HubComponent
    deployment_active: bool
    deployment_status: ComponentDeploymentStatus
    deployment_capacity: str
    deployment_log_level: str
    deployment_restart_policy: str
    deployment_updated_at: Optional[str]
    compute_node: Optional[str]

    def get_deployment_hash(self) -> str:
        return str(
            hash(
                json.dumps(
                    {
                        "input": self.input,
                        "capacity": self.deployment_capacity,
                        "log_level": self.deployment_log_level,
                        "restart_policy": self.deployment_restart_policy,
                    }
                )
            )
        )

    def update_status(self):
        self._rest_client.patch(
            f"v2/engine/component/components/{self.id}/",
            data={"deployment_status": self.deployment_status},
        )
        logger.info(
            f"Component {self.id} updated with status {self.deployment_status}"
        )

    def refresh(self):
        response = self._rest_client.get(
            f"v2/engine/component/components/{self.id}/"
        )
        response.raise_for_status()
        data = response.json()
        for field in self.__fields__.values():
            if field.name in data:
                setattr(self, field.name, data[field.name])

    def __str__(self) -> str:
        return f"Component(id={self.id}, name={self.name}, deployment_active={self.deployment_active}))"


class ComputeNode(APIObject):
    id: str
    name: Optional[str]

    @property
    def components(self):
        response = self._rest_client.get(
            f"v2/engine/compute_node/{self.id}/components/",
        )
        return [Component(**c) for c in response.json()]


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
    component: Component


class DeployedComponent(BaseModel):
    container: Container
    component_id: str
    deployment_hash: str

    class Config:
        arbitrary_types_allowed = True