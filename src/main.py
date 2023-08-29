import logging
import os

from splight_agent.handlers import ComponentHandler
from splight_agent.settings import settings

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL)

if __name__ == "__main__":
    if not settings.COMPUTE_NODE_ID:
        raise Exception("COMPUTE_NODE_ID is not set")

    component_handler = ComponentHandler()

    try:
        component_handler.poll_forever()
    except KeyboardInterrupt:
        component_handler.stop_polling()
        logging.info("Agent stopped")
        exit(0)
