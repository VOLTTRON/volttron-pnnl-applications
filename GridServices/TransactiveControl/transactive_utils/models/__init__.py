import importlib
import logging
from volttron.platform.agent import utils
from volttron.platform.agent.math_utils import mean, stdev

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"

__all__ = ['Model']


class Model(object):
    def __init__(self, config, **kwargs):
        self.model = None
        config = self.store_model_config(config)
        self.cleared_quantity = None
        if not config:
            return
        base_module = "transactive_utils.models."
        try:
            model_type = config["model_type"]
        except KeyError as e:
            _log.exception("Missing Model Type key: {}".format(e))
            raise e
        _file, model_type = model_type.split(".")
        module = importlib.import_module(base_module + _file)
        self.model_class = getattr(module, model_type)
        self.model = self.model_class(config, self)

    def get_q(self, _set, sched_index, market_index, occupied):
        q = self.model.predict(_set, sched_index, market_index, occupied)
        return q

    def store_model_config(self, _config):
        try:
            config = self.vip.config.get("model")
        except KeyError:
            config = {}
        try:
            self.vip.config.set("model", _config, send_update=False)
        except RuntimeError:
            _log.debug("Cannot change config store on config callback!")
        _config.update(config)
        return _config

    def update_prediction(self, quantity):
        if self.model is not None:
            _log.debug("Update cleared quantity %s -- %s", quantity, self.prediction_error)
        if self.prediction_error is not None and quantity is not None:
            self.cleared_quantity = quantity/self.prediction_error
        else:
            self.cleared_quantity = quantity

    def update_prediction_error(self):
        prediction_data = getattr(self.model, "prediction_data", None)
        if prediction_data is None:
            _log.debug("Prediction data not available for correction!")
            return
        if self.cleared_quantity is None:
            _log.debug("Cleared quantity data is not available for correction!")
            return
        try:
            average_quantity = mean(self.model.prediction_data)
        except:
            _log.debug("Problem finding average prediction data: %s", self.model.prediction_data)
            return
        _log.debug("Update prediction error %s -- %s -- %s", self.model.prediction_data, average_quantity, self.cleared_quantity)
        self.model.prediction_data = []
        if self.cleared_quantity > 0:
            self.prediction_error = average_quantity/self.cleared_quantity
        else:
            self.prediction_error = 1.0

