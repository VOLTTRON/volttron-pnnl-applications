import logging

from volttron.platform.agent import utils
import transactive_utils.models.input_names as data_names
from transactive_utils.models.utils import clamp

_log = logging.getLogger(__name__)
utils.setup_logging()


class simple(object):
    def __init__(self, config, parent, **kwargs):
        self.parent = parent
        self.inputs = parent.inputs
        self.rated_power = config["rated_power"]

    def update_data(self):
        pass

    def predict(self, _set, sched_index, market_index, occupied):
        return _set*self.rated_power


class simple_profile(object):
    def __init__(self, config, parent, **kwargs):
        self.parent = parent
        self.inputs = parent.inputs
        self.rated_power = config["rated_power"]
        try:
            self.lighting_schedule = config["default_lighting_schedule"]
        except KeyError:
            _log.warning("No no default lighting schedule!")
            self.lighting_schedule = [1.0]*24

    def update_data(self):
        pass

    def predict(self, _set, sched_index, market_index, occupied):
        if not occupied:
            power = self.lighting_schedule[sched_index]*self.rated_power
        else:
            power = _set*self.rated_power
        return power
