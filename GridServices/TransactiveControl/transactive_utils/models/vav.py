"""
Copyright (c) 2020, Battelle Memorial Institute
All rights reserved.
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
The views and conclusions contained in the software and documentation are those
of the authors and should not be interpreted as representing official policies,
either expressed or implied, of the FreeBSD Project.
This material was prepared as an account of work sponsored by an agency of the
United States Government. Neither the United States Government nor the United
States Department of Energy, nor Battelle, nor any of their employees, nor any
jurisdiction or organization that has cooperated in th.e development of these
materials, makes any warranty, express or implied, or assumes any legal
liability or responsibility for the accuracy, completeness, or usefulness or
any information, apparatus, product, software, or process disclosed, or
represents that its use would not infringe privately owned rights.
Reference herein to any specific commercial product, process, or service by
trade name, trademark, manufacturer, or otherwise does not necessarily
constitute or imply its endorsement, recommendation, or favoring by the
United States Government or any agency thereof, or Battelle Memorial Institute.
The views and opinions of authors expressed herein do not necessarily state or
reflect those of the United States Government or any agency thereof.

PACIFIC NORTHWEST NATIONAL LABORATORY
operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
"""

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
