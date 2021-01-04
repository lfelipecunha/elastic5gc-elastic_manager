import logging
import logging.config
import sys
import os

class Logger:
    config = {}
    
    logger = None

    file = None

    def __init__(self, package_name):
        config = Logger.config
        logger = logging.getLogger(package_name)

        handler = logging.StreamHandler(sys.stdout)

        filename = config.get('filename', None)
        if not filename is None:
            handler = logging.FileHandler(filename)
        
        loglevel = config.get('level', 'ERROR')
        if not isinstance(loglevel, str):
            _error(loglevel)
            
        numeric_level = getattr(logging, loglevel.upper(), None)
        if not isinstance(numeric_level, int):
            _error(loglevel)

        logger.setLevel(numeric_level)
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s] %(message)s')
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)

        self.logger = logger

    def debug(self, *args, **kw):
        return getattr(self.logger, "debug")(*args, **kw)

    def info(self, *args, **kw):
        return getattr(self.logger, "info")(*args, **kw)

    def error(self, *args, **kw):
        return getattr(self.logger, "error")(*args, **kw)

    def warning(self, *args, **kw):
        return getattr(self.logger, "warning")(*args, **kw)
    
    def critical(self, *args, **kw):
        return getattr(self.logger, "critical")(*args, **kw)

    def __del__(self):
        if not self.file is None:
            self.file.close()

    @classmethod
    def init_configs(cls, config):
        if not isinstance(config, dict):
            raise ValueError("Expect config as a dict. %s received", type(config))
        cls.config = config
        

def _error(loglevel):
    raise ValueError('Invalid log level: %s.\n\tMUST be: CRITICAL, ERROR, WARNING. INFO, DEBUG or NOTSET' % loglevel)
