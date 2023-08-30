import json
import logging
import time
from threading import Thread
from typing import List

import docker

from splight_agent.exporter import Exporter
from splight_agent.models import Component, ComputeNode, HubComponent
from splight_agent.settings import API_POLL_INTERVAL, settings


class ContainerActions:
    def __init__(self, exporter: Exporter) -> None:
        self.run: List[Component] = []
        self.stop: List[Component] = []
        self.restart: List[Component] = []
        self.do_nothing: List[Component] = []
        self._exporter = exporter

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

    def __str__(self) -> str:
        return (
            "ContainerActions:\n"
            + f"run: {self.run}\n"
            + f"stop: {self.stop}\n"
            + f"restart: {self.restart}\n"
            + f"do_nothing: {self.do_nothing}\n"
        )


class ComponentHandler:
    def __init__(self):
        self._compute_node = ComputeNode(id=settings.COMPUTE_NODE_ID)
        self._docker_client = docker.from_env()
        self._exporter = Exporter()
        self._exporter_thread = Thread(target=self._exporter.start, args=())
        self._exporter_thread.start()  # TODO: i don't like this thread
        self._components = {}
        self._container_actions = ContainerActions(exporter=self._exporter)

    def _get_component_tag(self, hub_component: HubComponent):
        name = hub_component.name.lower()
        return f"{name}-{settings.WORKSPACE_NAME}-{hub_component.version}"

    def _execute_run(self, component: Component):
        component_tag = self._get_component_tag(component.hub_component)

        # pull docker image
        # TODO: Maybe add retry?
        try:
            image_file = component.hub_component.get_image_file()
        except Exception:
            logging.error(
                f"Failed to get image url for component {component.name}"
            )
            return

        self._docker_client.images.load(image_file)
        image = self._docker_client.images.get(
            f"{settings.ECR_REPOSITORY}:{component_tag}"
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
                "SPLIGHT_GRPC_HOST": settings.SPLIGHT_GRPC_HOST,
                "LOG_LEVEL": "0",
                "COMPONENT_ID": component.id,
            },
            network_mode="host",  # TODO: delete after testing
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
            try:
                self._container_actions.update_lists(
                    self._compute_node.components
                )
            except Exception:
                logging.error("Failed to update container actions")
                time.sleep(API_POLL_INTERVAL)
                continue
            logging.info(self._container_actions)
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
