from io import BytesIO

import requests
from furl import furl
from tqdm import tqdm
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

    def get(self, path: str) -> requests.Response:
        return requests.get(self._base_url / path, headers=self.headers)

    def patch(self, path: str, data: dict) -> requests.Response:
        return requests.patch(
            self._base_url / path, json=data, headers=self.headers
        )

    def download(self, path: str, external: bool = True) -> bytes:
        url = path if external else self._base_url / path
        with requests.get(url, stream=True) as download:
            pbar = tqdm(
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                total=int(download.headers["Content-Length"]),
                ncols=120,
            )
            pbar.clear()
            bytes = BytesIO()
            for chunk in download.iter_content(chunk_size=512):
                if chunk:
                    bytes.write(chunk)
                    pbar.update(len(chunk))
            content = bytes.getvalue()
            download.raise_for_status()
            pbar.close()
            return content
