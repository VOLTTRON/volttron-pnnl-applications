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
        config = self.get_model_config(config)
        self.cleared_quantity = None
        self.prediction_error = 1.0
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

    def get_q(self, _set, market_time, occupied, realtime=False):
        q = self.model.predict(_set, market_time, occupied, realtime=realtime)
        return q

    def get_model_config(self, _config):
        try:
            config = self.vip.config.get("model")
        except KeyError:
            config = {}
        if config:
            _config.update(config)
        return _config

    def store_model_config(self, config):
        _log.debug("MODEL STORE: {}".format(config))
        try:
            self.vip.config.set("model", config, send_update=False)
        except RuntimeError:
            _log.debug("Cannot change config store on config callback!")

    def update_prediction(self, quantity):
        if self.model is not None:
            _log.debug("Update cleared quantity %s -- %s", quantity, self.prediction_error)
        #if self.prediction_error is not None and quantity is not None:
        #    self.cleared_quantity = quantity/self.prediction_error
        #else:
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
        if self.cleared_quantity > 0 and average_quantity > 0:
            self.prediction_error = average_quantity/self.cleared_quantity
        else:
            self.prediction_error = 1.0
        message = {"Factor": self.prediction_error}
        suffix = "PredictionCorrection"
        try:
            self.publish_record(suffix, message)
        except Exception as e:
            _log.debug("ERROR - publishing correction factor: {}".format(e))


