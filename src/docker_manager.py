import docker
from typing import List
import logger

from infrastructure_manager import InfrastructureManagerStrategy

class DockerCommunicationHandler:
    def __init__ (self, host, port):
        self.host = host
        self.port = port
        self.logger = _get_logger()

        self.logger.info("New Docker HOST http://%s:%s", host, port)
        self.client = docker.DockerClient(base_url='http://'+host+':'+str(port))

    def get_containers(self, container_filter=[]):
        return self.client.containers.list(filters=container_filter)

    def create_container(self, image_name, command, **kwargs):
        kwargs['detach'] = True
        return self.client.containers.run(image_name, command, **kwargs)

class DockerHost:
    host = ''
    port = 0
    service_label = ''
    nrf_ip = ''
    image_name =  ''
    container_config = {}
    command = ''
    amf_url = ''

    def __init__(self, host_config:dict, service_config:dict):
        self.logger = _get_logger()
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
        self.set_param('amf_url', service_config)
        self.set_param('image_name', service_config)
        self.set_param('command', host_config)

    def set_param(self, param, config, required=True, default=None):
        setattr(self, param, config.get(param, default))
        if required and getattr(self, param) == None:
            raise Exception('DockerCommunicationHandler', 'configuration \''+ param +'\' not found!')
        self.logger.debug("Set param \"%s\" to \"%s\"", param, config.get(param, default))

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

        amf_url = self.amf_url.replace("{{AMFID}}", service_id)
        self.logger.debug("AMF URL %s", amf_url)
        configs['environment'] = ["AMF_IP="+amf_url, 'NRF_URI='+str(self.nrf_ip)]
        configs['labels'] = {self.service_label: str(service_id)}
        configs['alias'] = amf_url

        container = self.docker_handler.create_container(self.image_name, self.command, **configs)
        self.logger.debug('Added container: %s', container)
        self.running_services.append(container)

    def remove_service(self):
        size = self.get_amount_running_services()
        self.logger.debug('Amount running services: %s', size)
        if size > 0:
            container = self.running_services.pop()
            container.stop()
            container.remove()
            return True
        self.logger.info('Nothing to remove')
        return False


class DockerManager(InfrastructureManagerStrategy):

    def __init__(self, hosts:List[DockerHost]):
        super(DockerManager, self).__init__()
        self.hosts = hosts
        self.logger = _get_logger()

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
                id = self.generate_id()
                self.logger.debug('New service id [%s]', id)
                host.add_service(id)
                added = True
                break
        if not added:
            self.logger.warning('Maximum amount of services reached!')
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
        if not removed:
            self.logger.warning('Nothing to remove!')
        return removed


docker_manager_logger = None
def _get_logger():
    global docker_manager_logger
    if docker_manager_logger is None:
        docker_manager_logger = logger.Logger('DockerManager')
    return docker_manager_logger