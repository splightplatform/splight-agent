import base64
import boto3
import subprocess
from splight_agent.schemas import Command, Component, HubComponent
from splight_agent.settings import settings, SPLIGHT_HOME
import docker
from threading import Thread
from splight_agent.exporter import Exporter
from splight_lib.restclient import SplightRestClient
from splight_lib.auth.token import SplightAuthToken
from furl import furl
import json


class CommandHandler:
    def __init__(self):
        self._base_url = furl(settings.SPLIGHT_PLATFORM_API_HOST)
        self._client = SplightRestClient()
        token = SplightAuthToken(
            access_key=settings.SPLIGHT_ACCESS_ID,
            secret_key=settings.SPLIGHT_SECRET_KEY,
        )
        self._client.update_headers(token.header)
        self._docker_client = docker.from_env()
        self._login_to_ecr()
        self._exporter = Exporter()
        self._exporter_thread = Thread(target=self._exporter.start, args = ())
        self._exporter_thread.start() # TODO: i don't like this thread

    def _login_to_ecr(self):
        """ Login to ECR (this shouldn't be needed) """
        ecr_client = boto3.client('ecr', region_name='us-east-1')
        token = ecr_client.get_authorization_token()
        username, password = base64.b64decode(token['authorizationData'][0]['authorizationToken']).decode().split(':')
        registry = token['authorizationData'][0]['proxyEndpoint']
        self._docker_client.login(username, password, registry=registry)

    def _get_component_tag(self, hub_component: HubComponent):
        name = hub_component.name.lower()
        return f"{name}-{settings.WORKSPACE_NAME}-{hub_component.version}"

    def _execute_run(self, command: Command):
        response = self._client.get(
            self._base_url / f"v2/engine/component/components/{command.component_id}/"
        )
        if response.status_code != 200:
            raise Exception("Component not found")
        component = Component.parse_obj(response.json())
        component_tag = self._get_component_tag(component.hub_component)

        # pull docker image
        image = self._docker_client.images.pull(
            repository=settings.ECR_REPOSITORY, tag=component_tag
        )


        # run docker image
        run_spec = json.dumps(
            {
                "name": component.hub_component.name,
                "version": component.hub_component.version,
                "input": component.input,
            }
        )
        container = self._docker_client.containers.run(
            image,
            detach=True,
            environment={
                "NAMESPACE": settings.NAMESPACE,
                "SPLIGHT_ACCESS_ID": settings.SPLIGHT_ACCESS_ID,
                "SPLIGHT_SECRET_KEY": settings.SPLIGHT_SECRET_KEY,
                "SPLIGHT_PLATFORM_API_HOST": settings.SPLIGHT_PLATFORM_API_HOST,
                "SPLIGHT_GRPC_HOST": "integrationgrpc.splight-ai.com:443",
                "LOG_LEVEL": "0",
                "COMPONENT_ID": command.component_id,
            },
            network_mode='host', # TODO: delete after testing
            remove=False,
            command=["python", "runner.py", "-r", run_spec],
        )
        self._exporter.add_container(command.component_id, container)

    def _execute_stop(self, command: Command):
        container = self._exporter.get_container(command.component_id)
        if container:
            container.stop()
            self._exporter.remove_container(command.component_id)

    def execute(self, command: Command):
        if command.action == "run":
            self._execute_run(command)
        elif command.action == "stop":
            self._execute_stop(command)
        else:
            raise NotImplementedError()
