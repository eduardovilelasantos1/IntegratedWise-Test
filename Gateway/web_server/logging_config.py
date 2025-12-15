import logging
import os

LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

def setup_logger(name):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        '%(asctime)s %(name)s %(levelname)s: %(message)s'
    )

    fh = logging.FileHandler(os.path.join(LOG_DIR, 'webserver.log'))
    fh.setFormatter(formatter)

    sh = logging.StreamHandler()
    sh.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(sh)

    return logger
