from abc import ABC, abstractmethod

class InfrastructureManagerStrategy(ABC):

    def __init__ (self):
        self.cur_id = 0

    def generate_id(self):
        self.cur_id += 1
        return self.cur_id

    @abstractmethod
    def add_service(self) -> bool:
        pass

    @abstractmethod
    def remove_service(self) -> bool:
        pass

    @abstractmethod
    def get_running_services(self) -> bool:
        pass
