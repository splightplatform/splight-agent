from splight_agent.engine import Engine
from splight_agent.dispatcher import Dispatcher
from splight_agent.exporter import Exporter

from splight_agent.logging import get_logger
from splight_agent.settings import settings

logger = get_logger(__name__)

if __name__ == "__main__":
    if not settings.COMPUTE_NODE_ID:
        raise Exception("COMPUTE_NODE_ID is not set")

    exporter = Exporter()
    exporter.start()

    engine = Engine()
    dispatcher = Dispatcher(engine)
    try:
        dispatcher.start()
    except KeyboardInterrupt:
        logger.info("Agent stopped")
