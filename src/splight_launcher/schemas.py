from pydantic import BaseModel
from typing import Any, List, Optional, Dict

class Command(BaseModel):
    action: str
    component_id: str

# Component
### (only the fields that are needed for the launcher)
class HubComponent(BaseModel):
    id: str
    name: str
    version: str
    custom_types: List[Dict[str, Any]]
    input: List[Dict[str, Any]]
    output: List[Dict[str, Any]]
    commands: List[Dict[str, Any]]
    endpoints: List[Dict[str, Any]]
    bindings: List[Dict[str, Any]]


class Component(BaseModel):
    id: str
    name: str
    input: List[Dict[str, Any]]
    hub_component: HubComponent