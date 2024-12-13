import logging
import threading

class ThreadSafeLogger:
    _lock = threading.Lock()

    @classmethod
    def log(cls, level, message):
        with cls._lock:
            if level == 'info':
                logging.info(message)
            elif level == 'warning':
                logging.warning(message)
            elif level == 'error':
                logging.error(message)
s
