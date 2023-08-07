from splight_lib.restclient import SplightRestClient
from splight_agent.settings import settings
from splight_lib.auth.token import SplightAuthToken
from splight_agent.handlers import CommandHandler
from splight_agent.schemas import Command
from furl import furl
import time

# TODO: should we implement database_client in agent?
COMPUTE_NODES_URL = "v2/engine/compute_node/"
COMPUTE_NODE_COMPONENTS_URL = COMPUTE_NODES_URL + "{compute_node}/components/"

if __name__ == "__main__":
    base_url = furl(settings.SPLIGHT_PLATFORM_API_HOST)
    client = SplightRestClient()
    token = SplightAuthToken(
        access_key=settings.SPLIGHT_ACCESS_ID,
        secret_key=settings.SPLIGHT_SECRET_KEY,
    )
    client.update_headers(token.header)
    command_handler = CommandHandler()

    if not settings.AGENT_ID:
        # create agent
        response = client.post(base_url / COMPUTE_NODES_URL, data={"name": settings.AGENT_NAME})
        settings.AGENT_ID = response.json().get('id')
        settings.save()

    
    # pooling
    try:
        while True:
            response = client.get(base_url / COMPUTE_NODE_COMPONENTS_URL.format(compute_node=settings.AGENT_ID))
            new_commands = [Command.parse_obj(task.get('command')) for task in response.json()]
            print('new commands: ', new_commands)
            for command in new_commands:
                command_handler.execute(command)
            time.sleep(5)
    except KeyboardInterrupt:
        pass