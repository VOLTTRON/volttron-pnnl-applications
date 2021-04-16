import logging
from volttron.platform.agent import utils
from dateutil.parser import parse
from transactive_utils.models.utils import clamp
import transactive_utils.models.input_names as data_names

_log = logging.getLogger(__name__)
utils.setup_logging()


class firstorderzone(object):
    def __init__(self, config, parent, **kwargs):
        self.parent = parent
        self.a1 = config.get("a1", 0)
        self.a2 = config.get("a2", 0)
        self.a3 = config.get("a3", 0)
        self.a4 = config.get("a4", 0)
        self.coefficients = {"a1", "a2", "a3", "a4"}
        type = config.get("terminal_box_type", "VAV")
        self.get_input_value = parent.get_input_value
        # parent mapping
        # data inputs
        self.oat_name = data_names.OAT
        self.sfs_name = data_names.SFS
        self.zt_name = data_names.ZT
        self.zdat_name = data_names.ZDAT
        self.zaf_name = data_names.ZAF
        self.oat = self.get_input_value(self.oat_name)
        self.sfs = self.get_input_value(self.sfs_name)
        self.zt = self.get_input_value(self.zt_name)

        self.zt_predictions = [self.zt]*24
        if type.lower() == "vav":
            self.parent.commodity = "ZoneAirFlow"
            self.predict_quantity = self.getM
        else:
            self.parent.commodity = "DischargeAirTemperature"
            self.predict_quantity = self.getT

    def update_coefficients(self, coefficients):
        if set(coefficients.keys()) != self.coefficients:
            _log.warning("Missing required coefficient to update model")
            _log.warning("Provided coefficients %s -- required %s",
                         list(coefficients.keys()), self.coefficients)
            return
        self.a1 = coefficients["a1"]
        self.a2 = coefficients["a2"]
        self.a3 = coefficients["a3"]
        self.a4 = coefficients["a4"]
        message = {
            "a1": self.a1,
            "a2": self.a2,
            "a3": self.a3,
            "a4": self.a4
        }
        topic_suffix = "MODEL_COEFFICIENTS"
        self.parent.publish_record(topic_suffix, message)

    def update_data(self):
        pass

    def update(self, _set, market_time):
        _log.debug("update_state: {} - {} - {}".format(_set, market_time, self.zt_predictions))
        index = market_time.hour
        self.zt_predictions[index] = _set

    def predict(self, _set, market_time, occupied, realtime=False):
        index = parse(market_time).hour
        if realtime:
            oat = self.get_input_value(self.oat_name)
            sfs = self.get_input_value(self.sfs_name)
            zt = self.get_input_value(self.zt_name)
            occupied = sfs if sfs is not None else occupied
        else:
            zt_index = index - 1 if index > 0 else 23
            zt = self.zt_predictions[zt_index]
            oat = self.get_input_value(self.oat_name)
            if market_time in self.parent.oat_predictions:
                _log.debug("OAT NOT IN PREDICTIONS! %s -- %s", market_time, self.parent.oat_predictions)
                oat = self.parent.oat_predictions[market_time]
        q = 0.0
        if oat is not None and zt is not None:
            _log.debug("OAT: %s -- ZT: %s", oat, zt)
            q = self.predict_quantity(oat, zt, _set, index)

        _log.debug(
            "%s: vav.firstorderzone q: %s - zt: %s- set: %s - sched: %s",
            self.parent.agent_name, q, zt, _set, index
        )
        # might need to revisit this when doing both heating and cooling
        if occupied:
            q = clamp(q, min(self.parent.flexibility), max(self.parent.flexibility))
        else:
            q = 0.0
        return q

    def getT(self, oat, temp, temp_stpt, index):
        T = temp_stpt*self.a1[index]+temp*self.a2[index]+oat*self.a3[index]+self.a4[index]
        return T

    def getM(self, oat, temp, temp_stpt, index):
        M = temp_stpt*self.a1[index]+temp*self.a2[index]+oat*self.a3[index]+self.a4[index]
        return M
