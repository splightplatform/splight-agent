from pydantic import BaseModel
from typing import Any, List, Optional, Dict
from splight_agent.settings import settings
from splight_lib.restclient import SplightRestClient
from splight_lib.auth.token import SplightAuthToken


class RestClientModel(BaseModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client = SplightRestClient()
        token = SplightAuthToken(
            access_key=settings.SPLIGHT_ACCESS_ID,
            secret_key=settings.SPLIGHT_SECRET_KEY,
        )
        self._client.update_headers(token.header)
        self._base_url = settings.SPLIGHT_PLATFORM_API_HOST

# Component
### (only the fields that are needed for the agent)
class HubComponent(BaseModel):
    id: str
    name: str
    version: str

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
        """ only comparing attributes that are important for the deployment """
        if not isinstance(__value, Component):
            return NotImplemented
        
        return (
            self.input == __value.input
            and self.deployment_active == __value.deployment_active
            and self.deployment_capacity == __value.deployment_capacity
            and self.deployment_log_level == __value.deployment_log_level
            and self.deployment_restart_policy == __value.deployment_restart_policy
        )
    
    def update_status(self, status: str):
        self._client.patch(
            self._base_url / f"v2/engine/component/{self.id}/",
            json={"deployment_status": status},
        )
        self.deployment_status = status
        print(f"Component {self.name} status updated to {status}")

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
        return [Component(**c) for c in response.json()]