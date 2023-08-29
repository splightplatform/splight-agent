import gzip
import logging
import shutil
from tempfile import NamedTemporaryFile
from typing import Any, Dict, List, Optional

import requests
from furl import furl
from pydantic import BaseModel, PrivateAttr
from splight_lib.auth.token import SplightAuthToken
from splight_lib.restclient import SplightRestClient

from splight_agent.settings import settings


class RestClientModel(BaseModel):
    _client: SplightRestClient = PrivateAttr()
    _base_url: furl = PrivateAttr()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client = SplightRestClient()
        token = SplightAuthToken(
            access_key=settings.SPLIGHT_ACCESS_ID,
            secret_key=settings.SPLIGHT_SECRET_KEY,
        )
        self._client.update_headers(token.header)
        self._base_url = furl(settings.SPLIGHT_PLATFORM_API_HOST)


# Component
### (only the fields that are needed for the agent)
class HubComponent(RestClientModel):
    id: str
    name: str
    version: str

    def get_image_file(self):
        response = self._client.post(
            self._base_url / f"v2/hub/download/image_url/",
            json={"name": self.name, "version": self.version},
        )
        # download file
        if response.status_code != 200:
            if response.json() and "detail" in response.json():
                raise Exception(
                    f"Error getting image url for component {self.name}: {response.json()['detail']}"
                )
            raise Exception(
                f"Error getting image url for component {self.name}"
            )
        logging.info("Downloding image file")
        response_file = requests.get(response.json()["url"])
        if response_file.status_code != 200:
            raise Exception(
                f"Error downloading image for component {self.name}"
            )
        return response_file.content


class Component(RestClientModel):
    id: str
    name: str
    input: List[Dict[str, Any]]
    hub_component: HubComponent
    deployment_active: bool
    deployment_status: str
    deployment_capacity: str
    deployment_log_level: str
    deployment_restart_policy: str
    deployment_updated_at: str
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

    def update_status(self, status: str):
        response = self._client.patch(
            self._base_url / f"v2/engine/component/{self.id}/",
            json={"deployment_status": status},
        )
        if response.status_code != 200:
            if response.json() and "detail" in response.json():
                raise Exception(
                    f"Error getting components for compute node {self.id}: {response.json()['detail']}"
                )
            raise Exception(
                f"Error getting components for compute node {self.id}"
            )
        self.deployment_status = status
        logging.info(f"Component {self.name} status updated to {status}")

    def __str__(self) -> str:
        return f"Component(id={self.id}, name={self.name}, deployment_active={self.deployment_active}))"


class ComputeNode(RestClientModel):
    id: str
    name: Optional[str]

    @property
    def components(self):
        # TODO: add error management
        response = self._client.get(
            self._base_url / f"v2/engine/compute_node/{self.id}/components/"
        )
        if response.status_code != 200:
            if response.json() and "detail" in response.json():
                raise Exception(
                    f"Error getting components for compute node {self.id}: {response.json()['detail']}"
                )
            raise Exception(
                f"Error getting components for compute node {self.id}"
            )
        return [Component(**c) for c in response.json()]
