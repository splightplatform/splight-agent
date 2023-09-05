from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar

import requests
from furl import furl
from pydantic import BaseModel, PrivateAttr

from splight_agent.logging import get_logger
from splight_agent.settings import settings

logger = get_logger(__name__)


class RestClientModel(BaseModel):
    _base_url: furl = PrivateAttr()
    _headers: Dict[str, str] = PrivateAttr()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._base_url = furl(settings.SPLIGHT_PLATFORM_API_HOST)
        self._headers = {
            "Authorization": f"Splight {settings.SPLIGHT_ACCESS_ID} {settings.SPLIGHT_SECRET_KEY}"
        }


# Component
# (only the fields that are needed for the agent)
class HubComponent(RestClientModel):
    id: str
    name: str
    version: str

    def get_image_file(self):
        response = requests.post(
            self._base_url / f"v2/hub/download/image_url/",
            json={"name": self.name, "version": self.version},
            headers=self._headers,
        )
        response.raise_for_status()

        logger.info("Downloding image file")
        response_file = requests.get(response.json()["url"])
        response_file.raise_for_status()
        return response_file.content


class ContainerEventAction(str, Enum):
    CREATE = "create"
    START = "start"
    STOP = "stop"


class ComponentDeploymentStatus(str, Enum):
    PENDING = "Pending"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    STOPPED = "Stopped"
    UNKNOWN = "Unknown"


class Component(RestClientModel):
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

    def __eq__(self, __value: object) -> bool:
        """only comparing attributes that are important for the deployment"""
        if not isinstance(__value, Component):
            return NotImplemented

        return (
            self.input == __value.input
            and self.deployment_active == __value.deployment_active
            and self.deployment_capacity == __value.deployment_capacity
            and self.deployment_log_level == __value.deployment_log_level
            and self.deployment_restart_policy
            == __value.deployment_restart_policy
        )

    def update(self):
        response = requests.patch(
            self._base_url / f"v2/engine/component/components/{self.id}/",
            json={"deployment_status": self.deployment_status},
            headers=self._headers,
        )
        response.raise_for_status()
        logger.info(f"Component {self.id} updated with status {self.deployment_status}")

    def __str__(self) -> str:
        return f"Component(id={self.id}, name={self.name}, deployment_active={self.deployment_active}))"


class ComputeNode(RestClientModel):
    id: str
    name: Optional[str]

    @property
    def components(self):
        # TODO: add error management
        response = requests.get(
            self._base_url / f"v2/engine/compute_node/{self.id}/components/",
            headers=self._headers,
        )
        response.raise_for_status()
        return [Component(**c) for c in response.json()]


T = TypeVar("T", bound=BaseModel)


def partial(model: Type[T]) -> Type[T]:
    class OptionalModel(model):
        ...

    for field in OptionalModel.__fields__.values():
        field.required = False

    OptionalModel.__name__ = f"Optional{model.__name__}"

    return OptionalModel
