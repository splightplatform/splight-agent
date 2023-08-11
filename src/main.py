from splight_agent.settings import settings
from splight_agent.handlers import ComponentHandler

if __name__ == "__main__":
    if not settings.COMPUTE_NODE_ID:
        raise Exception("Agent ID not set")
    settings.save() # saving initial settings to file
    
    component_handler = ComponentHandler()

    try:
        component_handler.poll_forever()
    except KeyboardInterrupt:
        component_handler.stop_polling()
        print("Agent stopped")
        exit(0)
