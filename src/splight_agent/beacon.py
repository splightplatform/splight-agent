import time
from threading import Event, Thread
from typing import Protocol

from splight_agent.logging import SplightLogger
from splight_agent.models import ComputeNode
from splight_agent.rest_client import RestClient

logger = SplightLogger(__name__)


class BeaconSettings(Protocol):
    @property
    def API_PING_INTERVAL(self) -> int:
        ...


class Beacon:
    """
    The beacon periodically pings the API to signal that the agent is still alive
    """

    def __init__(self, compute_node: ComputeNode, ping_interval: int) -> None:
        self._ping_interval = ping_interval
        self._thread = Thread(target=self._ping_forever, daemon=True)
        self._stop = Event()
        self._client = RestClient()
        self._compute_node = compute_node

    def _ping(self):
        return self._client.post(
            f"v2/engine/compute_node/{self._compute_node.id}/healthcheck/", {}
        )

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    def _ping_forever(self):
        while True:
            if self.stopped:
                break
            try:
                self._ping()
            except Exception as e:
                logger.warning(f"Could not ping API: {e}")
            finally:
                time.sleep(self._ping_interval)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join()
