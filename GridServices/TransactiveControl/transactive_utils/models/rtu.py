import logging
import operator
import importlib
from volttron.platform.agent import utils
from transactive_utils.models.utils import clamp
import transactive_utils.models.input_names as data_names

_log = logging.getLogger(__name__)
utils.setup_logging()
OPS = {
    "csp": [(operator.gt, operator.add), (operator.lt, operator.sub)],
    "hsp": [(operator.lt, operator.sub), (operator.gt, operator.add)]
}


class firstorderzone(object):
    def __init__(self, config, parent, **kwargs):
        self.parent = parent
        self.c1 = config["c1"]
        self.c2 = config["c2"]
        self.c3 = config["c3"]
        self.c4 = config["c4"]
        self.coefficients = {"c1", "c2", "c3", "c4"}
        self.rated_power = config["rated_power"]

        self.on = [0]*24
        self.off = [0]*24

        self.predict_quantity = self.getQ
        self.smc_interval = parent.single_market_contol_interval
        self.get_input_value = parent.get_input_value

        # Initialize input data names from parent
        self.mclg_name = data_names.MC
        self.mhtg_name = data_names.MH
        self.oat_name = data_names.OAT
        self.sfs_name = data_names.SFS
        self.zt_name = data_names.ZT
        self.hsp_name = data_names.HSP
        self.csp_name = data_names.CSP

        # Initialize input data from parent
        self.oat = self.get_input_value(self.oat_name)
        self.zt = self.get_input_value(self.zt_name)
        self.csp = self.get_input_value(self.csp_name)
        self.hsp = self.get_input_value(self.hsp_name)
        self.mclg = self.get_input_value(self.mclg_name)
        self.mhtg = self.get_input_value(self.mhtg_name)
        self.sfs = self.get_input_value(self.sfs_name)
        self.zt_predictions = [self.zt] * 24
        self.configure(config)

    def update_data(self):
        self.oat = self.get_input_value(self.oat_name)
        self.zt = self.get_input_value(self.zt_name)
        self.mclg = self.get_input_value(self.mclg_name)
        self.mhtg = self.get_input_value(self.mhtg_name)
        self.csp = self.get_input_value(self.csp_name)
        self.hsp = self.get_input_value(self.hsp_name)
        self.sfs = self.get_input_value(self.sfs_name)
        if self.mclg is not None and self.mclg:
            self.on[0] += 1
            self.off[0] = 0
        elif self.mhtg is not None and self.mhtg:
            self.on[0] += 1
            self.off[0] = 0
        else:
            self.off[0] += 1
            self.on[0] = 0
        _log.debug("Update model data: oat: {} - zt: {} - mclg: {} - mhtg: {}".format(self.oat, self.zt, self.mclg, self.mhtg))

    def update(self, _set, sched_index, market_index, occupied):
        self.zt_predictions[market_index] = _set

    def configure(self, config):
        _log.debug("MODEL CONFIGURE: {}".format(config))
        self.c1 = config.get("c1", 0)
        self.c2 = config.get("c2", 0)
        self.c3 = config.get("c3", 0)
        self.c4 = config.get("c4", 0)
        # type = config.get("terminal_box_type", "VAV")
        # if type.lower() == "vav":
        #     self.parent.commodity = "ZoneAirFlow"
        #     self.predict_quantity = self.getM
        #     self.predict_name = self.zaf_name
        # else:
        #     self.parent.commodity = "DischargeAirTemperature"
        #     self.predict_quantity = self.getT
        #     self.predict_name = self.zdat_name

    def predict(self, _set, sched_index, market_index, occupied):
        if self.parent.market_number == 1:
            oat = self.oat
            zt = self.zt
            occupied = self.sfs if self.sfs is not None else occupied
            sched_index = self.parent.current_datetime.hour
        else:
            zt = self.zt_predictions[market_index]
            oat = self.parent.oat_predictions[market_index] if self.parent.oat_predictions else self.oat
        q = self.predict_quantity(oat, zt, _set, sched_index)
        _log.debug("{}: RTU predicted {} - zt: {} - set: {} - sched: {}".format(self.parent.agent_name, q, zt, _set, sched_index))
        # might need to revisit this when doing both heating and cooling
        if occupied:
            q = clamp(q, min(self.parent.flexibility), max(self.parent.flexibility))
            q = self.rated_power*q
        else:
            q = 0.0
        return q

    def getQ(self, oat, temp, temp_stpt, index):
        q = temp_stpt * self.c1[index] + temp * self.c2[index] + oat * self.c3[index] + self.c4[index]
        return q


class rtuzone(object):
    def __init__(self, config, parent, **kwargs):
        self.c1 = config["c1"]
        self.c2 = config["c2"]
        self.c3 = config["c3"]
        self.c = config["c"]
        self.coefficients = {"c1", "c2", "c3", "c"}
        self.parent = parent
        self.rated_power = config["rated_power"]
        self.on_min = config.get("on_min", 0)
        self.off_min = config.get("off_min", 0)
        self.tdb = config.get("temp_db", 0.5)
        self.tdb_on = config.get("temp_on_db", self.tdb)
        self.tdb_off = config.get("temp_off_db", self.tdb)
        self.on = [0]*parent.market_number
        self.off = [0]*parent.market_number

        self.predict = self.getQ
        self.parent.init_predictions = self.init_predictions
        self.smc_interval = parent.single_market_contol_interval
        self.get_input_value = parent.get_input_value
        self.check_future_schedule = parent.check_future_schedule

        # data inputs
        self.mclg_name = data_names.MC
        self.mhtg_name = data_names.MH
        self.oat_name = data_names.OAT
        self.zt_name = data_names.ZT
        self.csp_name = data_names.CSP
        self.predicting = "ZoneTemperature"

        self.oat = self.get_input_value(self.oat_name)
        self.zt = self.get_input_value(self.zt_name)
        self.csp = self.get_input_value(self.csp_name)
        self.mclg = self.get_input_value(self.mclg_name)
        self.mhtg = self.get_input_value(self.mhtg_name)
        self.zt_predictions = [self.zt] * parent.market_number
        if self.smc_interval is not None:
            self.zt_index = int(self.smc_interval)
        else:
            self.zt_index = int(self.parent.actuation_rate/60)

    def update_data(self):
        self.oat = self.get_input_value(self.oat_name)
        self.zt = self.get_input_value(self.zt_name)
        self.mclg = self.get_input_value(self.mclg_name)
        self.mhtg = self.get_input_value(self.mhtg_name)
        self.csp = self.get_input_value(self.csp_name)
        if self.mclg is not None and self.mclg:
            self.on[0] += 1
            self.off[0] = 0
        elif self.mhtg is not None and self.mhtg:
            self.on[0] += 1
            self.off[0] = 0
        else:
            self.off[0] += 1
            self.on[0] = 0
        _log.debug("Update model data: oat: {} - zt: {} - mclg: {} - mhtg: {}".format(self.oat, self.zt, self.mclg, self.mhtg))

    def update(self, _set, sched_index, market_index, occupied):
        q = self.predict(_set, sched_index, market_index, occupied, dc=False)

    def init_predictions(self, output_info):
        if self.parent.market_number == 1:
            return
        occupied = self.check_future_schedule(self.parent.current_datetime)

        if occupied:
            _set = output_info["value"]
        else:
            _set = self.parent.off_setpoint
        q = self.predict(_set, -1, -1, occupied, False)

    def getQ(self, temp_stpt, sched_index, market_index, occupied, dc=True):
        if self.parent.market_number == 1:
            oat = self.oat
            zt = self.zt
            runtime = self.parent.single_market_contol_interval
            ontime = self.on[0]
            offtime = self.off[0]
            sched_index = self.parent.current_datetime.hour
        elif market_index == -1:
            runtime = int(60 - self.parent.current_datetime.minute)
            ontime = self.on[0]
            offtime = self.off[0]
            sched_index = self.parent.current_datetime.hour
            oat = self.oat
            zt = self.zt
        else:
            zt = self.zt_predictions[market_index]
            oat = self.parent.oat_predictions[market_index] if self.parent.oat_predictions else self.parent.get_input_value(self.oat)
            ontime = self.on[market_index]
            offtime = self.off[market_index]
            runtime = 60

        if self.parent.mapped is not None:
            ops = OPS[self.parent.mapped]
        else:
            ops = OPS["csp"]

        # assumption here is device is transitioning from cooling to off
        # or from heating to off in an hour.  No hour will contain both
        # heating and cooling.  (valid?)
        on = 0
        getT = self.getT
        on_condition = ops[0][0]
        on_operator = ops[0][1]
        off_condition = ops[1][0]
        off_operator = ops[1][1]
        prediction_array = [zt]
        for i in range(runtime):
            _log.debug("{} - temperature: {} - setpoint: {} - on: {} - current_time: {} - index: {} - loop: {}".format(
                self.parent.agent_name,
                zt,
                temp_stpt,
                on,
                self.parent.current_datetime,
                market_index,
                i))
            if ontime and off_condition(zt, off_operator(temp_stpt, self.tdb_off)) and ontime > self.on_min:
                offtime = 1
                ontime = 0
                zt = getT(zt, oat, 0, sched_index)
            elif ontime:
                offtime = 0
                ontime += 1
                on += 1
                zt = getT(zt, oat, 1, sched_index)
            elif offtime and on_condition(zt, on_operator(temp_stpt, self.tdb_on)) and offtime > self.off_min:
                offtime = 0
                ontime = 1
                on += 1
                zt = getT(zt, oat, 1, sched_index)
            else:
                offtime += 1
                ontime = 0
                zt = getT(zt, oat, 0, sched_index)
            prediction_array.append(zt)
        # need to revisit this code when heating and cooling are both considered
        if occupied:
            zt = clamp(zt, min(self.parent.flexibility), max(self.parent.flexibility))
        else:
            zt = clamp(zt, min(self.parent.flexibility), self.parent.off_setpoint)
        if (market_index + 1) < self.parent.market_number:
            self.on[market_index+1] = ontime
            self.off[market_index+1] = offtime
            self.zt_predictions[market_index + 1] = zt
        q = on/runtime*self.rated_power
        # Need to think about what we are actually publishing here and
        # if we can move it out of the model
        if not dc:
            topic_suffix = "/".join([self.parent.agent_name, "Prediction"])
            message = {"MarketIndex": market_index, self.predicting: prediction_array}
            self.parent.publish_record(topic_suffix, message)
        return q

    def getT(self, tpre, oat, on, index):
        T = (oat - tpre) * self.c1[index] - on * self.c2[index] * self.c + self.c3[index] + tpre
        return T