from splight_agent.beacon import Beacon
from splight_agent.dispatcher import Dispatcher
from splight_agent.engine import Engine
from splight_agent.exporter import Exporter
from splight_agent.logging import SplightLogger
from splight_agent.models import ComputeNode
from splight_agent.settings import SplightSettings

logger = SplightLogger(__name__)


class Orchestrator:
    _settings = SplightSettings()

    def __init__(self) -> None:
        compute_node = ComputeNode(id=self._settings.COMPUTE_NODE_ID)

        self._engine = Engine(
            compute_node=compute_node, settings=self._settings
        )
        self._beacon = Beacon(
            compute_node=compute_node, settings=self._settings
        )
        self._dispatcher = Dispatcher(
            compute_node=compute_node,
            engine=self._engine,
            settings=self._settings,
        )
        self._exporter = Exporter(compute_node=compute_node)

    def start(self):
        self._exporter.start()
        self._beacon.start()
        try:
            self._dispatcher.start()
        except KeyboardInterrupt:
            logger.info("Agent stopped")
