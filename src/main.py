from splight_lib.restclient import SplightRestClient
from splight_launcher.settings import settings
from splight_lib.auth.token import SplightAuthToken
from splight_launcher.handlers import CommandHandler
from splight_launcher.schemas import Command
from furl import furl
import time

# TODO: should we implement database_client in launcher?
LAUNCHERS_URL = "v2/engine/launchers/"
LAUNCHER_PENDING_TASKS_URL = LAUNCHERS_URL + "{launcher}/pending_tasks/"

if __name__ == "__main__":
    base_url = furl(settings.SPLIGHT_PLATFORM_API_HOST)
    client = SplightRestClient()
    token = SplightAuthToken(
        access_key=settings.SPLIGHT_ACCESS_ID,
        secret_key=settings.SPLIGHT_SECRET_KEY,
    )
    client.update_headers(token.header)
    command_handler = CommandHandler()

    if not settings.LAUNCHER_ID:
        # create launcher
        response = client.post(base_url / LAUNCHERS_URL, data={"name": settings.LAUNCHER_NAME})
        settings.LAUNCHER_ID = response.json().get('id')
        settings.save()

    
    # pooling
    try:
        while True:
            response = client.get(base_url / LAUNCHER_PENDING_TASKS_URL.format(launcher=settings.LAUNCHER_ID))
            new_commands = [Command.parse_obj(task.get('command')) for task in response.json()]
            print('new commands: ', new_commands)
            for command in new_commands:
                command_handler.execute(command)
            time.sleep(5)
    except KeyboardInterrupt:
        pass