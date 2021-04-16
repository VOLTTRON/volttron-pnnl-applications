import logging
from volttron.platform.agent import utils
from transactive_utils.models.utils import clamp
import transactive_utils.models.input_names as data_names

_log = logging.getLogger(__name__)
utils.setup_logging()

class uncontrol(object):
    def __init__(self, config, parent, **kwargs):
        self.parent = parent
        self.q_uc = config.get("default_power", [0]*24)
