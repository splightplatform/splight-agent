import time
from threading import Event, Thread

from splight_agent.logging import SplightLogger
from splight_agent.models import ComputeNode
from splight_agent.rest_client import RestClient
from splight_agent.settings import settings

logger = SplightLogger(__name__)


class Beacon:
    """
    The beacon periodically pings the API to signal that the agent is still alive
    """

    def __init__(self) -> None:
        self._thread = Thread(target=self._ping_forever, daemon=True)
        self._stop = Event()
        self._client = RestClient()
        self._compute_node = ComputeNode(id=settings.COMPUTE_NODE_ID)

    def _ping(self):
        logger.debug("Pinging API")
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
                time.sleep(settings.API_PING_INTERVAL)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join()
