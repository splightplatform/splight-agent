import time
from threading import Thread
from typing import Optional

import psutil
import shutil

from splight_agent.logging import SplightLogger
from splight_agent.models import ComputeNode, ComputeNodeUsage

logger = SplightLogger()


class UsageReporter:
    def __init__(
        self, compute_node: ComputeNode, cpu_percent_samples: Optional[int] = 4
    ) -> None:
        self._running = False
        self._compute_node = compute_node
        self._cpu_percent_samples = cpu_percent_samples
        self._thread = Thread(target=self._report_usage, daemon=True)

    def _get_cpu_percent(self) -> float:
        """Returns average cpu percent"""
        total = psutil.cpu_percent(interval=1)
        for i in range(self._cpu_percent_samples - 1):
            total += psutil.cpu_percent(interval=1)
        return total / self._cpu_percent_samples

    def _get_memory_percent(self) -> float:
        """Returns memory percent"""
        return psutil.virtual_memory().percent

    def _get_disk_percent(self) -> float:
        """Returns memory disk percent"""
        total, used, _ = shutil.disk_usage("/")
        return round(used / total * 100, 2)

    def _report_usage(self) -> None:
        while self._running:
            try:
                usage = ComputeNodeUsage(
                    compute_node=self._compute_node.id,
                    cpu_percent=self._get_cpu_percent(),
                    memory_percent=self._get_memory_percent(),
                    disk_percent=self._get_disk_percent(),
                )
                usage.save()
            except Exception as e:
                logger.error(f"Error while reporting usage: {e}")
            finally:
                time.sleep(60)

    def start(self):
        """
        Launch the usage reporter daemon thread
        """
        self._running = True
        self._thread.start()
        logger.info("Usage reporter started")

    def stop(self) -> None:
        """
        Stop the usage reporter daemon thread
        TODO: find a proper way to stop the thread
        """
        self._running = False
        logger.info("Usage reporter stopped")
