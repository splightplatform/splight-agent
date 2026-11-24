import time
from importlib import metadata
from threading import Event, Thread

from docker import from_env

from splight_agent.logging import SplightLogger
from splight_agent.models import ComputeNode
from splight_agent.rest_client import RestClient

logger = SplightLogger(__name__)


class Beacon:
    """
    The beacon periodically pings the API to signal that the agent is still alive
    """

    def __init__(
        self, compute_node: ComputeNode, ping_interval: int, api_version: str
    ) -> None:
        self._ping_interval = ping_interval
        self._thread = Thread(target=self._ping_forever, daemon=True)
        self._stop = Event()
        self._client = RestClient()
        self._compute_node = compute_node
        self._base_url = f"{api_version}/engine/compute/nodes/all"
        self._docker_client = from_env()
        self._agent_version = metadata.version("splight-agent")

    def _build_snapshot(self) -> dict:
        try:
            containers = self._docker_client.containers.list(
                all=True,
                filters={
                    "label": [
                        f"AgentID={self._compute_node.id}",
                        "ComponentID",
                    ]
                },
            )
            return {
                "agent_version": self._agent_version,
                "components": [
                    {
                        "id": container.labels["ComponentID"],
                        "container_status": container.status,
                        "health": container.attrs.get("State", {})
                        .get("Health", {})
                        .get("Status"),
                        "restart_count": container.attrs.get(
                            "RestartCount", 0
                        ),
                        "started_at": container.attrs.get("State", {}).get(
                            "StartedAt"
                        ),
                    }
                    for container in containers
                ],
            }
        except Exception as e:
            logger.warning(f"Could not build components snapshot: {e}")
            return {}

    def _ping(self):
        return self._client.post(
            f"{self._base_url}/{self._compute_node.id}/healthcheck/",
            self._build_snapshot(),
        )

    def _ping_forever(self):
        while True:
            if self._stop.is_set():
                break
            try:
                self._ping()
                logger.debug("API ping successful")
            except Exception as e:
                logger.warning(f"Could not ping API: {e}")
            finally:
                time.sleep(self._ping_interval)

    def start(self):
        logger.info("Beacon started")
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join()
