import base64
import time
from typing import List
import boto3
from splight_agent.models import Component, ComputeNode, HubComponent
from splight_agent.settings import settings, API_POLL_INTERVAL
import docker
from threading import Thread
from splight_agent.exporter import Exporter
import json

class ContainerActions:
    run: List = []
    stop: List = []
    restart: List = []
    do_nothing: List = []

    def __init__(self) -> None:
        self._exporter = Exporter() # I can do this since exporter is singleton

    def empty_lists(self):
        self.run = []
        self.stop = []
        self.restart = []
        self.do_nothing = []

    def update_lists(self, components: List[Component]):
        self.empty_lists()
        for component in components:
            if not component.deployment_active:
                if self._exporter.get_container(component.id):
                    self.stop.append(component)
                else:
                    self.do_nothing.append(component)
            else:
                running_component = self._exporter.get_component(component.id)
                if not running_component:
                    self.run.append(component)
                else:
                    if running_component != component:
                        self.restart.append(component)
                    else:
                        self.do_nothing.append(component)


class ComponentHandler:
    def __init__(self):
        self._compute_node = ComputeNode(id=settings.COMPUTE_NODE_ID)
        self._docker_client = docker.from_env()
        self._login_to_ecr()
        self._exporter = Exporter()
        self._exporter_thread = Thread(target=self._exporter.start, args = ())
        self._exporter_thread.start() # TODO: i don't like this thread
        self._components = {}
        self._container_actions = ContainerActions()

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

    def _execute_run(self, component: Component):
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
                "COMPONENT_ID": component.id,
            },
            network_mode='host', # TODO: delete after testing
            remove=False,
            command=["python", "runner.py", "-r", run_spec],
        )
        self._exporter.add_container(component, container)

    def _execute_stop(self, component):
        container = self._exporter.get_container(component.id)
        if container:
            container.stop()
            self._exporter.remove_container(component.id)


    def poll_forever(self):
        while True:
            self._container_actions.update_lists(self._compute_node.components)
            print(self._container_actions)
            for component in self._container_actions.run:
                self._execute_run(component)
            for component in self._container_actions.stop:
                self._execute_stop(component)
            for component in self._container_actions.restart:
                self._execute_stop(component)
                self._execute_run(component)
            time.sleep(API_POLL_INTERVAL)

    def stop_polling(self):
        self._exporter.stop()
        self._exporter_thread.join()

            
