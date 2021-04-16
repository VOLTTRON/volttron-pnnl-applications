import logging
from volttron.platform.agent import utils
from transactive_utils.models.utils import clamp
import transactive_utils.models.input_names as data_names

_log = logging.getLogger(__name__)
utils.setup_logging()


class firstorderzone(object):
    def __init__(self, config, parent, **kwargs):
        self.parent = parent
        self.a1 = 0
        self.a2 = 0
        self.a3 = 0
        self.a4 = 0
        self.coefficients = {"a1", "a2", "a3", "a4"}
        self.parent.commodity = "ZoneAirFlow"
        self.predict_quantity = self.getM
        self.prediction_data = []
        self.cleared_quantity = None
        self.get_input_value = parent.get_input_value

        # constants
        self.oat_name = data_names.OAT
        self.sfs_name = data_names.SFS
        self.zt_name = data_names.ZT
        self.zdat_name = data_names.ZDAT
        self.zaf_name = data_names.ZAF
        self.predict_name = self.zaf_name
        self.oat = self.get_input_value(self.oat_name)
        self.sfs = self.get_input_value(self.sfs_name)
        self.zt = self.get_input_value(self.zt_name)
        self.zt_predictions = [self.zt]*24
        self.configure(config)

    def configure(self, config):
        _log.debug("MODEL CONFIGURE: {}".format(config))
        self.a1 = config.get("a1", 0)
        self.a2 = config.get("a2", 0)
        self.a3 = config.get("a3", 0)
        self.a4 = config.get("a4", 0)
        type = config.get("terminal_box_type", "VAV")
        if type.lower() == "vav":
            self.parent.commodity = "ZoneAirFlow"
            self.predict_quantity = self.getM
            self.predict_name = self.zaf_name
        else:
            self.parent.commodity = "DischargeAirTemperature"
            self.predict_quantity = self.getT
            self.predict_name = self.zdat_name

    def update_data(self):
        zaf = self.get_input_value(self.zaf_name)
        if zaf is None:
            _log.debug("Cannot update prediction error ratio!  No data!")
            return
        self.prediction_data.append(zaf)
        _log.debug("Prediction data  zaf %s -- %s", zaf, self.prediction_data)

    def update(self, _set, sched_index, market_index):
        self.zt_predictions[market_index] = _set

    def predict(self, _set, sched_index, market_index, occupied):
        if self.parent.market_number == 1:
            oat = self.get_input_value(self.oat_name)
            sfs = self.get_input_value(self.sfs_name)
            zt = self.get_input_value(self.zt_name)
            occupied = sfs if sfs is not None else occupied
            sched_index = self.parent.current_datetime.hour
        else:
            zt = self.zt_predictions[market_index]
            if zt is None:
                zt = self.get_input_value(self.zt_name)

            if self.parent.oat_predictions:
                oat = self.parent.oat_predictions[market_index]
            else:
                oat = self.get_input_value(self.oat_name)
        q = self.predict_quantity(oat, zt, _set, sched_index)
        q_correct = q * self.parent.prediction_error
        _log.debug(
            "%s: vav.firstorderzone q: %s -  q_corrected %s- zt: %s- set: %s - sched: %s",
            self.parent.agent_name, q, q_correct, zt, _set, sched_index
        )
        # might need to revisit this when doing both heating and cooling
        if occupied:
            q = clamp(q_correct, min(self.parent.flexibility), max(self.parent.flexibility))
        else:
            q = 0.0
        return q

    def getT(self, oat, temp, temp_stpt, index):
        T = temp_stpt*self.a1[index]+temp*self.a2[index]+oat*self.a3[index]+self.a4[index]
        return T

    def getM(self, oat, temp, temp_stpt, index):
        M = temp_stpt*self.a1[index]+temp*self.a2[index]+oat*self.a3[index]+self.a4[index]
        return M
