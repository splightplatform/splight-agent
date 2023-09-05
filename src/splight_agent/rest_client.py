import requests
from furl import furl

from splight_agent.settings import settings


class RestClient:
    @property
    def _base_url(self) -> furl:
        return furl(settings.SPLIGHT_PLATFORM_API_HOST)

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Splight {settings.SPLIGHT_ACCESS_ID} {settings.SPLIGHT_SECRET_KEY}"
        }

    def post(self, path: str, data: dict) -> requests.Response:
        return requests.post(
            self._base_url / path, json=data, headers=self.headers
        )
