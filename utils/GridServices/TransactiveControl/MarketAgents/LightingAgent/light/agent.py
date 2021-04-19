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

import sys
import numpy as np
import logging
from volttron.platform.agent import utils
from transactive_utils.transactive_base.transactive import TransactiveBase


_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.3"

LTL = "light"
OCC = "occ"


class LightAgent(TransactiveBase):
    """
    Transactive control lighting agent.
    """

    def __init__(self, config_path, **kwargs):
        try:
            config = utils.load_config(config_path)
        except StandardError:
            config = {}
        self.agent_name = config.get("agent_name", "light_control")
        TransactiveBase.__init__(self, config, **kwargs)
        # TODO: Will update this to have on parameter control both mag and rate of control change
        self.ramp_rate = config.get("control_ramp_rate", 0.02)
        self.current_control = None
        self.default_lighting_schedule = config["model_parameters"].get("default_lighting_schedule", [0.9] * 24)
        self.decrease_load_only = config.get("decrease_load_only", False)

    def determine_control(self, sets, prices, price):
        """
        prices is an list of 11 elements, evenly spaced from the smallest price
        to the largest price and corresponds to the y-values of a line.  sets
        is an np.array of 11 elements, evenly spaced from the control value at
        the lowest price to the control value at the highest price and
        corresponds to the x-values of a line.  Price is the cleared price.
        :param sets: np.array;
        :param prices: list;
        :param price: float
        :return:
        """
        _log.debug("Updated determine_control! -- %s", self.current_datetime)
        default_control = None
        if self.current_datetime is not None:
            _hour = self.current_datetime.hour
            default_control = self.default_lighting_schedule[_hour]

        if self.current_control is None:
            if default_control is None:
                self.current_control = np.mean(self.ct_flexibility)
            else:
                self.current_control = default_control
        
        control_final = np.interp(price, prices, sets)
        _log.debug("determine_control -- current - %s -- final - %s -- default - %s", self.current_control, control_final, default_control)
        if self.current_control is not None:
            if self.current_control < control_final:
                self.current_control = min(self.ramp_rate + self.current_control, control_final)
            elif self.current_control > control_final:
                self.current_control = max(self.current_control - self.ramp_rate, control_final)
            else:
                self.current_control = control_final
        if self.decrease_load_only and default_control is not None:
            if self.current_control > default_control:
                self.current_control = default_control

        return self.current_control

    def init_predictions(self, output_info):
        pass

    def update_state(self, market_time, market_index, occupied, price, prices):
        self.update_flag[market_index] = True


def main():
    """Main method called to start the agent."""
    utils.vip_main(LightAgent, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
