import shutil
import time
from threading import Thread
from typing import Optional

import psutil

from splight_agent.logging import SplightLogger
from splight_agent.models import ComputeNode, ComputeNodeLatency
from splight_agent.rest_client import RestClient

logger = SplightLogger()


class LatencyReporter:
    def __init__(
        self, compute_node: ComputeNode, api_version: str) -> None:
        self._running = False
        self._compute_node = compute_node
        self._client = RestClient()
        self._base_url = f"{api_version}/engine/compute/nodes/all"
        self._thread = Thread(target=self._report_latency, daemon=True)
    
    
    def _ping(self):
        return self._client.get(
            f"{self._base_url}/{self._compute_node.id}/ping/",
            {},
        )
    
    def _get_latency_to_API(self) -> float:
        try:
            start = time.monotonic()
            self._ping()
            end = time.monotonic()
            return (end - start) * 1000
        except Exception as e:
                logger.warning(f"Could not ping API: {e}")


    def _report_latency(self) -> None:
        while self._running:
            try:
                latency = ComputeNodeLatency(
                    compute_node=self._compute_node.id,
                    latency=self._get_latency_to_API()
                )
                latency.save()
            except Exception as e:
                logger.error(f"Error while reporting latency: {e}")
            finally:
                time.sleep(60)

    def start(self):
        """
        Launch the latency reporter daemon thread
        """
        self._running = True
        self._thread.start()
        logger.info("Latency reporter started")

    def stop(self) -> None:
        """
        Stop the latency reporter daemon thread
        TODO: find a proper way to stop the thread
        """
        self._running = False
        logger.info("Latency reporter stopped")
