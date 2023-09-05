from functools import cached_property, partial
import time
from threading import Thread

import requests

from splight_agent.logging import get_logger
from splight_agent.models import ComputeNode
from splight_agent.rest_client import RestClient
from splight_agent.settings import settings, API_PING_INTERVAL

logger = get_logger(__name__)


class Beacon:
    """
    The beacon periodically pings the API to signal that the agent is still alive
    """

    def __init__(self, compute_node: ComputeNode) -> None:
        self._thread = Thread(target=self._ping, daemon=True)
        self._compute_node = compute_node

    @cached_property
    def _client(self) -> RestClient:
        return RestClient()

    def _ping(self):
        return self._client.post(f"v2/engine/compute_node/{self.id}/components/", {})

    def _send_pings(self):
        while True:
            try:
                self._ping()
            except Exception as e:
                logger.warning(f"Could not ping API: {e}")
            finally:
                time.sleep(API_PING_INTERVAL)
