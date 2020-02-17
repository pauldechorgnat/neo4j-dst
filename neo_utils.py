import docker
import time
import os
from neo4j import GraphDatabase


class DockerDriver(object):
    def __init__(self,
                 image_name,
                 network_name='bridge',
                 version='latest',
                 environment_variables=None,
                 volumes=None,
                 detach=True):
        # storing values for later use
        self.image_name = image_name
        self.network_name = network_name
        self.version = version
        self.environment_variables = environment_variables
        self.detach = detach

        # parsing volumes information
        self.volumes = {k: {'bind': v, 'mode': 'rw'} for k, v in volumes.items()} if volumes is not None else None

        # name and tag of the image
        self.container_image_tag = '{}:{}'.format(image_name, version)

        # name of the docker instance
        self.container_name = '{}_{}'.format(image_name, time.time())

        # creating a docker client
        self.docker_client = docker.from_env()

        # initializing container information
        self.container = None
        self.container_ip = None
        self.network = self.docker_client.networks.get(self.network_name)

        # initializing a driver
        self.driver = None

    def launch_container(self):
        self.container = self.docker_client.containers.run(image=self.container_image_tag,
                                                           name=self.container_name,
                                                           environment=self.environment_variables,
                                                           volumes=self.volumes,
                                                           network=self.network_name,
                                                           detach=self.detach
                                                           )

    def get_container_ip(self):

        network = self.docker_client.networks.get(self.network_name)
        containers = network.attrs['Containers']
        container_ip = None

        for c in containers.keys():
            if containers[c]['Name'] == self.container_name:
                container_ip = containers[c]['IPv4Address'].split('/')[0]
        if container_ip is None:
            raise ValueError('IP of the container not found.')
        self.container_ip = container_ip
        return container_ip

    def stop_container(self):
        self.container.stop()
        self.container.remove()

    def create_driver(self):
        raise NotImplementedError


class Neo4JForDockerDriver(DockerDriver):
    def __init__(self,
                 user='neo4j',
                 password='password',
                 volume_data='data_for_neo4j',
                 volume_import='/home/paul/data_for_graph',
                 volume_logs='logs_for_neo4j',
                 env_variables=None,
                 network_name='bridge',
                 version='3.5.7'):
        # https://neo4j.com/developer/docker-run-neo4j/
        # storing values
        self.user = user
        self.password = password
        self.volume_data = os.path.join(os.getcwd(), volume_data)
        self.volume_import = volume_import
        self.volume_logs = os.path.join(os.getcwd(), volume_logs)

        # dealing with environment variables
        environment_variables = {'NEO4J_AUTH': '{}/{}'.format(user, password)}
        if env_variables:
            for name, env in env_variables:
                environment_variables[name] = env

        volumes = {self.volume_data: '/data',
                   self.volume_import: '/import',
                   self.volume_logs: '/logs'}

        DockerDriver.__init__(self,
                              image_name='neo4j',
                              network_name=network_name,
                              version=version,
                              environment_variables=environment_variables,
                              volumes=volumes,
                              detach=True
                              )

    def stop_container(self):
        self.driver.close()
        DockerDriver.stop_container(self)

    def create_driver(self):
        time.sleep(5)
        host = self.get_container_ip()
        self.driver = GraphDatabase.driver('bolt://{}:7687'.format(host),
                                           auth=(self.user, self.password))
        return self.driver

    def session(self, access_mode=None, **parameters):
        if self.driver is not None:
            return self.driver.session(access_mode=access_mode, **parameters)


