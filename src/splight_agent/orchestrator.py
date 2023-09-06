from types import FrameType

from splight_agent.beacon import Beacon
from splight_agent.dispatcher import Dispatcher
from splight_agent.engine import Engine
from splight_agent.exporter import Exporter
from splight_agent.logging import SplightLogger
from splight_agent.settings import settings

logger = SplightLogger(__name__)


class MissingComputeNodeIdError(Exception):
    ...


class Orchestrator:
    def __init__(self) -> None:
        self._engine = Engine()
        self._exporter = Exporter()
        self._beacon = Beacon()
        self._dispatcher = Dispatcher(self._engine)

    def check_settings(self):
        if not settings.COMPUTE_NODE_ID:
            raise MissingComputeNodeIdError("COMPUTE_NODE_ID is not set")

    def start(self):
        self._exporter.start()
        self._beacon.start()
        self._dispatcher.start()

    def kill(self, sig: int, frame: FrameType):
        logger.info(f"Received signal {sig}. Gracefully stopping Agent...")
        # Stopping components
        stopped_components = self._engine.stop_all()
        logger.info(f"Stopped {len(stopped_components)} components")
        logger.info("Waiting for components to be stopped in the platform...")
        self._dispatcher.wait_for_components_to_stop(stopped_components)
        logger.info("All components stopped")
        self._beacon.stop()
        self._exporter.stop()
