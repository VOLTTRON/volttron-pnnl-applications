import logging
import importlib
import sys
import pandas as pd
from volttron.platform.agent import utils
from datetime import timedelta as td
from volttron.pnnl.models.utils import clamp

_log = logging.getLogger(__name__)
utils.setup_logging()


class simple(object):
    def __init__(self, config, parent, **kwargs):
        self.parent = parent
        self.inputs = parent.inputs

    def update_data(self):
        pass

    def predict(self, _set, sched_index, market_index, occupied):
        pass

