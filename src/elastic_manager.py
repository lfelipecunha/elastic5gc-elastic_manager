import time
import os
import http.client
import json
from statsmodels.tsa.arima.model import ARIMA
import yaml
import argparse

from infrastructure_manager import InfrastructureManagerStrategy
from docker_manager import DockerHost, DockerManager

import logger

class ElasticManager:

    def __init__(self, infra_manager:InfrastructureManagerStrategy, manager_config, monitor_config):
        thresholds = manager_config.get('thresholds', {})
        self.upper = thresholds.get('upper', 70)
        self.lower = thresholds.get('lower', 30)
        arima_conf = manager_config.get('arima', {})
        self.arima = {
            'p': arima_conf.get('p', 1),
            'd': arima_conf.get('d', 0),
            'q': arima_conf.get('q', 0)
        }
        self.minimal_monitorings = manager_config.get('minimal_monitorings', 10)
        self.minimal_services = manager_config.get('minimal_services', 1)
        self.running_services = 0
        self.monitor_config = monitor_config
        self.lookahead = manager_config.get('lookahead', 10)
        self.infra_manager = infra_manager
        self.last_sequency = None
        self.logger = logger.Logger('ElasticManager')

    def initialize(self):
        self.running_services = self.infra_manager.get_running_services()
        self.logger.info('Running services: %s', self.running_services)

        if self.minimal_services > self.running_services:
            for i in range(self.running_services, self.minimal_services):
                self.add_service()


    def start_new_monitoring(self):
        self.last_sequency = None
        sequencies = self.get_entries(1)
        if (len(sequencies) > 0):
            self.last_sequency = sequencies.pop().get('_id', None)

    def get_entries(self, quantity, initial_sequency=None):

        conn = http.client.HTTPConnection(self.monitor_config['host'], self.monitor_config['port'])
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

            self.logger.debug('Serie [Len: %s] %s', len(serie), serie)

            if len(serie) >= self.minimal_monitorings:
                self.load_prediction(serie)
            time.sleep(self.monitor_config['interval'])

    def load_prediction(self, series):
        model = ARIMA(series, order=(self.arima['p'],self.arima['d'],self.arima['q']))
        res = model.fit()
        forecast = res.forecast(self.lookahead)
        self.logger.debug('Forecast: %s', forecast[self.lookahead-1])
        return self.elastic_action_evaluator(forecast[self.lookahead-1])

    def elastic_action_evaluator(self, total_cpu):
        action_taken = False
        if (total_cpu > self.upper):
            action_taken = self.add_service()
        elif (total_cpu < self.lower):
            action_taken = self.remove_service()

        if action_taken:
            self.start_new_monitoring()

    def add_service(self):
        self.logger.info('Adding Service')
        added = False
        if self.infra_manager.add_service():
            self.running_services += 1
            added=True
        else:
            self.logger.warning('Cannot add service')

        return added

    def remove_service(self):
        removed = False
        self.logger.info('Removing Service')
        if (self.running_services > self.minimal_services):
            if self.infra_manager.remove_service():
                self.running_services -= 1
                removed = True
            else:
                self.logger.warning('Cannot remove service')
        else:
            self.logger.warning('Not removed! Minimal of %s services', self.minimal_services)

        return removed

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Elastic Manager')
    parser.add_argument('--config', help="Configuration File")
    args = parser.parse_args()

    yml_file = open(os.path.abspath(os.path.join(os.path.abspath(__file__), '..', args.config)))
    config = yaml.load(yml_file, Loader=yaml.CLoader)

    logger.Logger.init_configs(config.get('logger', {}))

    service_config = config.get('service_config', {})
    docker_hosts = []
    for host_config in config.get('docker_hosts', []):
        docker_host = DockerHost(host_config, service_config)
        docker_hosts.append(docker_host)

    docker_manager = DockerManager(docker_hosts)
    em = ElasticManager(docker_manager, config.get('manager', {}), config.get('monitor', {'host': 'localhost', 'port': 5000, 'interval': 2}))
    em.initialize()
    em.collect_and_sumarize()
