from typing import Dict, TypeVar
from pydantic import BaseModel
from splight_agent.models import partial
from splight_agent.settings import settings
import furl
import requests


class RestClient:

    @property
    def base_url(self) -> furl:
        return furl(settings.SPLIGHT_PLATFORM_API_HOST)

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Splight {settings.SPLIGHT_ACCESS_ID} {settings.SPLIGHT_SECRET_KEY}"
        }

    def post(self, path: str, data: dict) -> requests.Response:
        return requests.post(self._base_url / path, json=data, headers=self.headers)
