import time
import os
import http.client
import json
from statsmodels.tsa.arima.model import ARIMA

class ElasticManager:

    def __init__(self):
        self.upper = 70
        self.lower = 30
        self.minimal_monitorings = 10
        self.minimal_services = 1
        self.running_services = 0
        self.monitor_interval = int(os.environ['MONITOR_INTERVAL'])
        self.steps = 10

    def initialize(self):
        return None

    def collect_and_sumarize(self):
        while(True):
            conn = http.client.HTTPConnection(os.environ['MONITOR_HOST'], os.environ['MONITOR_PORT'])
            conn.request('GET', '/entries/'+str(self.minimal_monitorings))
            response = conn.getresponse().read().decode()
            sequencies = json.loads(response)
            serie = []
            for seq in sequencies:
                total = 0
                for entry in seq['entries']:
                    total += float(entry['cpu_usage'])
                serie.append(total/seq['count'])

            self.log('serie', serie)
            self.log('Len', len(serie))

            if len(serie) >= self.minimal_monitorings:
                self.load_prediction(serie)
            time.sleep(self.monitor_interval)

    def load_prediction(self, series):
        model = ARIMA(series, order=(5,1,0))
        res = model.fit()
        forecast = res.forecast(self.steps)
        self.log('forecast', forecast[self.steps-1])
        return self.elastic_action_evaluator(forecast[self.steps-1])

    def elastic_action_evaluator(self, totalCpu):
        if (totalCpu > self.upper):
            self.add_service()
        elif (totalCpu < self.lower):
            self.remove_service()

    def add_service(self):
        self.log('Adding Service', None)
        # @TODO create communication with services manager
        self.running_services += 1

    def remove_service(self):
        self.log('Removind Service', None)
        # @TODO create communication with services manager
        if (self.running_services > self.minimal_services):
            self.running_services -= 1

    def log(self, label, value):
        print('[' + str(int(time.time())) + '][' + label + '] - ' + str(value), flush=True)


if __name__ == "__main__":
    py = ElasticManager()
    py.initialize()
    py.collect_and_sumarize()

