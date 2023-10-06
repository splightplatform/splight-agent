from io import BytesIO

import requests
from furl import furl

from splight_agent.logging import SplightLogger
from splight_agent.settings import settings

logger = SplightLogger(__name__)


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

    def get(self, path: str) -> requests.Response:
        response = requests.get(self._base_url / path, headers=self.headers)
        response.raise_for_status()
        return response

    def patch(self, path: str, data: dict) -> requests.Response:
        response = requests.patch(
            self._base_url / path, json=data, headers=self.headers
        )
        response.raise_for_status()
        return response

    def download(self, path: str, external: bool = True) -> bytes:
        url = path if external else self._base_url / path
        logger.info("Starting download...")
        with requests.get(url, stream=True) as download:
            total = int(download.headers["Content-Length"])
            bytes = BytesIO()
            chunk_size = total // 20
            for chunk in download.iter_content(chunk_size=chunk_size):
                if chunk:
                    logger.info(
                        f"Downloading... {round((bytes.tell() / total) * 100, 2) }%"
                    )
                    bytes.write(chunk)
            content = bytes.getvalue()
            download.raise_for_status()
            logger.info("Download complete")
            return content
