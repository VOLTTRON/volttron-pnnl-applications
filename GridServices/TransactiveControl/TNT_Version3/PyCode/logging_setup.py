import logging
import os

IS_VOLTTRON = True
try:
    from volttron.platform.agent import utils
except ImportError:
    IS_VOLTTRON = False


def get_log_handle():
    if IS_VOLTTRON:
        utils.setup_logging()
        _log = logging.getLogger(__name__)
    else:
        _log = setup_logging()
    return _log


def setup_logging(name, log_file=None, level=logging.DEBUG):
    home = os.path.expanduser("~")
    if log_file is None:
        log_file = f"home/tent.log"
    handler = logging.FileHandler(log_file)
    fmt = '%(asctime)s %(name)s %(levelname)s: %(message)s'
    handler.setFormatter(logging.Formatter(fmt))

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger
