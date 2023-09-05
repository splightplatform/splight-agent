from beacon import Beacon
from dispatcher import Dispatcher
from engine import Engine
from exporter import Exporter

from splight_agent.logging import get_logger
from splight_agent.settings import settings

logger = get_logger(__name__)


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
        try:
            self._dispatcher.start()
        except KeyboardInterrupt:
            logger.info("Agent stopped")
