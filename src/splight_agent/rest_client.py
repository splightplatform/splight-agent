import sys
from typing import Optional

import requests
import wget
from furl import furl

from splight_agent.logging import SplightLogger
from splight_agent.settings import settings

logger = SplightLogger(__name__)


def bar_progress(current: float, total: float, width: int = 80):
    progress_message = "Downloading: %d%% [%d / %d] bytes" % (
        current / total * 100,
        current,
        total,
    )
    sys.stdout.write("\r" + progress_message)
    sys.stdout.flush()


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
        response = requests.post(
            self._base_url / path, json=data, headers=self.headers
        )
        response.raise_for_status()
        return response

    def get(self, path: str, params: dict=None) -> requests.Response:
        response = requests.get(self._base_url / path, headers=self.headers, params=params)
        response.raise_for_status()
        return response

    def patch(self, path: str, data: dict) -> requests.Response:
        response = requests.patch(
            self._base_url / path, json=data, headers=self.headers
        )
        response.raise_for_status()
        return response

    def download(
        self, path: str, external: bool = True, file_path: Optional[str] = None
    ) -> str:
        url = path if external else self._base_url / path
        logger.info("Starting download...")
        downloaded_file = wget.download(url, out=file_path, bar=bar_progress)
        sys.stdout.write("\n")
        logger.info("Download complete")
        return downloaded_file
