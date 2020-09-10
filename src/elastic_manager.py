import time
import os
import http.client
import json
from statsmodels.tsa.arima.model import ARIMA
import yaml

from infrastructure_manager import InfrastructureManagerStrategy
from docker_manager import DockerHost, DockerManager

class ElasticManager:

    def __init__(self, infra_manager:InfrastructureManagerStrategy):
        self.upper = 70
        self.lower = 30
        self.minimal_monitorings = 10
        self.minimal_services = 1
        self.running_services = 0
        self.monitor_interval = int(os.environ['MONITOR_INTERVAL'])
        self.steps = 10
        self.infra_manager = infra_manager
        self.last_sequency = None

    def initialize(self):
        self.running_services = self.infra_manager.get_running_services()
        print('Running service:', self.running_services)

        if self.minimal_services > self.running_services:
            for i in range(self.running_services, self.minimal_services):
                self.add_service()


    def start_new_monitoring(self):
        self.last_sequency = None
        sequencies = self.get_entries(1)
        if (len(sequencies) > 0):
            self.last_sequency = sequencies.pop().get('_id', None)

    def get_entries(self, quantity, initial_sequency=None):

        conn = http.client.HTTPConnection(os.environ['MONITOR_HOST'], os.environ['MONITOR_PORT'])
        path = '/entries/'+str(quantity)
        if initial_sequency != None:
            path += '?initial_sequency=' + initial_sequency

        conn.request('GET', path)
        response = conn.getresponse().read().decode()
        return json.loads(response)

    def collect_and_sumarize(self):
        self.start_new_monitoring()
        while(True):
            sequencies = self.get_entries(self.minimal_monitorings, self.last_sequency)
            serie = []
            for seq in sequencies:
                total = 0
                for entry in seq['entries']:
                    total += float(entry['cpu_usage'])
                serie.insert(0, total/seq['count'])

            self.log('DEBUG','serie ' + str(serie))
            self.log('DEBUG','Len ' + str(len(serie)))

            if len(serie) >= self.minimal_monitorings:
                self.load_prediction(serie)
            time.sleep(self.monitor_interval)

    def load_prediction(self, series):
        model = ARIMA(series, order=(1,0,0))
        res = model.fit()
        forecast = res.forecast(self.steps)
        self.log('DEBUG', 'forecast ' + str(forecast[self.steps-1]))
        return self.elastic_action_evaluator(forecast[self.steps-1])

    def elastic_action_evaluator(self, total_cpu):
        action_taken = False
        if (total_cpu > self.upper):
            action_taken = self.add_service()
        elif (total_cpu < self.lower):
            action_taken = self.remove_service()

        if action_taken:
            self.start_new_monitoring()

    def add_service(self):
        self.log('INFO', 'Adding Service')
        added = False
        if self.infra_manager.add_service():
            self.running_services += 1
            added=True
        else:
            self.log('ERROR', 'Cannot add service')

        return added

    def remove_service(self):
        removed = False
        self.log('INFO','Removind Service')
        if (self.running_services > self.minimal_services):
            if self.infra_manager.remove_service():
                self.running_services -= 1
                removed = True
            else:
                self.log('ERROR', 'Cannot remove service')
        else:
            self.log('INFO', 'Not removed! Minimal of '+str(self.minimal_services)+' services.')

        return removed

    def log(self, label, value):
        print('[' + str(int(time.time())) + '][' + label + '] - ' + str(value), flush=True)


if __name__ == "__main__":
    yml_file = open(os.path.abspath(os.path.join(os.path.abspath(__file__), '../../config/elastic_manager.yml')))
    config = yaml.load(yml_file, Loader=yaml.CLoader)
    service_config = config.get('service_config', {})
    docker_hosts = []
    for host_config in config.get('docker_hosts', []):
        docker_host = DockerHost(host_config, service_config)
        docker_hosts.append(docker_host)

    docker_manager = DockerManager(docker_hosts)
    em = ElasticManager(docker_manager)
    em.initialize()
    em.collect_and_sumarize()

