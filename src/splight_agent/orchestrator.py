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
        try:
            self._dispatcher.start()
        except KeyboardInterrupt:
            logger.info("Agent stopped")
