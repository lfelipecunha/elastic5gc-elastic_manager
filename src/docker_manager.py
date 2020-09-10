import docker
from typing import List

from infrastructure_manager import InfrastructureManagerStrategy

class DockerCommunicationHandler:
    def __init__ (self, host, port):
        self.host = host
        self.port = port
        self.client = docker.DockerClient(base_url='http://'+host+':'+str(port))

    def get_containers(self, container_filter=[]):
        return self.client.containers.list(filters=container_filter)

    def create_container(self, image_name, command, **kwargs):
        kwargs['detach'] = True
        return self.client.containers.run(image_name, command, **kwargs)

class DockerHost:
    def __init__(self, host_config:dict, service_config:dict):
        self.parse_configs(host_config, service_config)
        self.docker_handler = DockerCommunicationHandler(self.host, self.port)
        self.running_services = []

    def parse_configs(self, host_config, service_config):
        self.set_param('max_services', host_config)
        self.set_param('host', host_config)
        self.set_param('port', host_config)
        self.set_param('container_config', host_config, False)
        self.set_param('service_label', service_config, False, 'amf')
        self.set_param('nrf_ip', service_config)
        self.set_param('image_name', service_config)

    def set_param(self, param, config, required=True, default=None):
        setattr(self, param, config.get(param, default))
        if required and getattr(self, param) == None:
            raise Exception('DockerCommunicationHandler', 'configuration \''+ param +'\' not found!')

    def get_amount_running_services(self):
        return len(self.running_services)

    def get_running_services(self):
        container_filter = {'label': self.service_label}
        self.running_services = self.docker_handler.get_containers(container_filter)

        return self.get_amount_running_services()

    def add_service(self, service_id):
        configs = {}
        if self.container_config != None:
            configs = self.container_config
        configs['environment'] = ['AMF_NAME=AMF'+str(service_id), 'NRF_IP='+str(self.nrf_ip)]
        configs['labels'] = {self.service_label: str(service_id)}

        container = self.docker_handler.create_container(self.image_name, './amf -amfgcf ../config/amfcfg.conf', **configs)
        print(container)
        self.running_services.append(container)

    def remove_service(self):
        size = self.get_amount_running_services()
        if size > 0:
            container = self.running_services.pop()
            container.stop()
            container.remove()
            return True
        return False


class DockerManager(InfrastructureManagerStrategy):

    def __init__(self, hosts:List[DockerHost]):
        super(DockerManager, self).__init__()
        self.hosts = hosts

    def get_running_services(self):
        quantity=0
        for host in self.hosts:
            quantity += host.get_running_services()
        return quantity


    def add_service(self):
        added = False
        for host in self.hosts:
            services_count = host.get_amount_running_services()
            if services_count < host.max_services:
                host.add_service(self.generate_id())
                added = True
                break
        return added

    def remove_service(self):
        removed = False
        for i in reversed(range(len(self.hosts))):
            host = self.hosts[i]
            services_count = host.get_amount_running_services()
            if services_count > 0:
                if host.remove_service():
                    removed = True
                    break
        return removed
