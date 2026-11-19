import time
from importlib import metadata
from threading import Event, Thread

import requests
from docker import from_env

from splight_agent.logging import SplightLogger
from splight_agent.models import ComputeNode
from splight_agent.rest_client import RestClient

logger = SplightLogger(__name__)

IMDS_URL = "http://169.254.169.254/latest"


def _get_instance_id() -> str | None:
    try:
        token = requests.put(
            f"{IMDS_URL}/api/token",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"},
            timeout=2,
        )
        token.raise_for_status()
        response = requests.get(
            f"{IMDS_URL}/meta-data/instance-id",
            headers={"X-aws-ec2-metadata-token": token.text},
            timeout=2,
        )
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.warning(f"Could not read EC2 instance id: {e}")
        return None


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
        self._instance_id = _get_instance_id()

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
                "instance_id": self._instance_id,
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
