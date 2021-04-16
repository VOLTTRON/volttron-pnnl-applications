import importlib
import logging
from volttron.platform.agent import utils

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"

__all__ = ['Model']


class Model(object):
    def __init__(self, config, **kwargs):
        if not config:
            self.model = None
            return
        base_module = "transactive_utils.models." #"volttron_pnnl_applications.GridServices.TransactiveControl.market_base.models."
        try:
            model_type = config["model_type"]
        except KeyError as e:
            _log.exception("Missing Model Type key: {}".format(e))
            raise e
        _file, model_type = model_type.split(".")
        module = importlib.import_module(base_module + _file)
        model_class = getattr(module, model_type)
        self.model = model_class(config, self)

    def get_q(self, _set, market_time, occupied, realtime=False):
        q = self.model.predict(_set, market_time, occupied, realtime=realtime)
        return q
