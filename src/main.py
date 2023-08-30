import os

from splight_agent.handlers import ComponentHandler
from splight_agent.logging import get_logger
from splight_agent.settings import settings

logger = get_logger(__name__)

if __name__ == "__main__":
    if not settings.COMPUTE_NODE_ID:
        raise Exception("COMPUTE_NODE_ID is not set")

    component_handler = ComponentHandler()

    try:
        component_handler.poll_forever()
    except KeyboardInterrupt:
        component_handler.stop_polling()
        logger.info("Agent stopped")
        exit(0)
