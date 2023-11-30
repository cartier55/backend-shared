import logging
import colorlog
import inspect
import os


class Logger:
    def __init__(self, logger_name, file_name="./logs/app.log"):
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.DEBUG)
        
        formatter = colorlog.ColoredFormatter(
            '%(asctime)s - %(name)s - %(log_color)s%(levelname)s%(reset)s - [%(module)s:%(funcName)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors={
                'DEBUG': 'reset',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        
        # Log to file
        self.file_handler = logging.FileHandler(file_name, encoding='utf-8')
        self.file_handler.setLevel(logging.DEBUG)
        self.file_handler.setFormatter(formatter)
        self.logger.addHandler(self.file_handler)
        
        # Log to console
        self.console_handler = logging.StreamHandler()
        self.console_handler.setLevel(logging.DEBUG)
        self.console_handler.setFormatter(formatter)
        self.logger.addHandler(self.console_handler)

    def _get_caller_info(self):
        stack = inspect.stack()
        frame = stack[3]  # Changed from 2 to 3
        module = inspect.getmodule(frame[0])
        module_name = "" if module is None else module.__name__
        func_name = frame.function
        return module_name, func_name


    def _log(self, level, message, silent=False):
        module_name, func_name = self._get_caller_info()
        if silent:
            self.logger.removeHandler(self.console_handler)
        
        # Create a LogRecord manually
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            module_name,
            0,  # Line number, not necessary
            message,
            None,
            None,
            func_name
        )
        self.logger.handle(record)
        
        if silent:
            self.logger.addHandler(self.console_handler)



    def log_info(self, message, silent=False):
        self._log(logging.INFO, message, silent)

    def log_error(self, message):
        self._log(logging.ERROR, message)

    def log_warning(self, message):
        self._log(logging.WARNING, message)

    def log_debug(self, message):
        self._log(logging.DEBUG, message)

    def log_critical(self, message):
        self._log(logging.CRITICAL, message)

log_file_path = os.path.join(os.path.dirname(__file__), 'Logs', 'coachify.log')
coach_logger = Logger("coach_logger", log_file_path)
