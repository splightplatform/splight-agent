import sys
from types import FrameType

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

    @property
    def _compute_node(self) -> ComputeNode:
        return ComputeNode(id=self._settings.COMPUTE_NODE_ID)

    def _create_engine(self) -> Engine:
        return Engine(
            compute_node=self._compute_node,
            workspace_name=self._settings.WORKSPACE_NAME,
            ecr_repository=self._settings.ECR_REPOSITORY,
            componenent_environment={
                "NAMESPACE": self._settings.NAMESPACE,
                "SPLIGHT_ACCESS_ID": self._settings.SPLIGHT_ACCESS_ID,
                "SPLIGHT_SECRET_KEY": self._settings.SPLIGHT_SECRET_KEY,
                "SPLIGHT_PLATFORM_API_HOST": self._settings.SPLIGHT_PLATFORM_API_HOST,
                "SPLIGHT_GRPC_HOST": self._settings.SPLIGHT_GRPC_HOST,
            },
        )

    def _create_beacon(self) -> Beacon:
        return Beacon(
            compute_node=self._compute_node,
            ping_interval=self._settings.API_PING_INTERVAL,
        )

    def _create_exporter(self) -> Exporter:
        return Exporter(compute_node=self._compute_node)

    def _create_dispatcher(self, engine: Engine) -> Dispatcher:
        return Dispatcher(
            compute_node=self._compute_node,
            engine=engine,
            poll_interval=self._settings.API_POLL_INTERVAL,
        )

    def __init__(self) -> None:
        self._engine = self._create_engine()
        self._beacon = self._create_beacon()
        self._exporter = self._create_exporter()
        self._dispatcher = self._create_dispatcher(self._engine)

    def start(self):
        self._exporter.start()
        self._beacon.start()
        self._dispatcher.start()

    def kill(self, sig: int, frame: FrameType):
        logger.info(f"Received signal {sig}. Gracefully stopping Agent...")
        stopped_components = self._engine.stop_all()
        logger.info(f"Stopped {len(stopped_components)} components")
        logger.info("Waiting for components to be stopped in the platform...")
        self._dispatcher.wait_for_components_to_stop(stopped_components)
        logger.info("All components stopped")
        self._beacon.stop()
        self._exporter.stop()
        sys.exit(0)
