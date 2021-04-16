# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# }}}

import os
import sys
import logging
from datetime import datetime, timedelta
from dateutil import parser
import numpy as np

from volttron.platform.vip.agent import Agent, Core, PubSub, RPC, compat
from volttron.platform.agent import utils
from volttron.platform.agent.utils import (get_aware_utc_now, format_timestamp)

from timer import Timer
from generator import Generator

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'


class CityAgent(Agent):
    def __init__(self, config_path, **kwargs):
        Agent.__init__(self, **kwargs)

        self.config_path = config_path
        self.config = utils.load_config(config_path)
        self.name = self.config.get('name')
        self.T = int(self.config.get('T', 24))

        self.db_topic = self.config.get("db_topic", "tnc")
        self.campus_demand_topic = "{}/campus/city/demand".format(self.db_topic)
        self.city_supply_topic = "{}/city/campus/supply".format(self.db_topic)

        self.simulation = self.config.get('simulation', False)
        self.simulation_start_time = parser.parse(self.config.get('simulation_start_time'))
        self.simulation_one_hour_in_seconds = int(self.config.get('simulation_one_hour_in_seconds'))

        Timer.created_time = datetime.now()
        Timer.simulation = self.simulation
        Timer.sim_start_time = self.simulation_start_time
        Timer.sim_one_hr_in_sec = self.simulation_one_hour_in_seconds

        # Initialization
        self.error_energy_threshold = float(self.config.get('error_energy_threshold'))
        self.error_reserve_threshold = float(self.config.get('error_reserve_threshold'))
        self.alpha_energy = float(self.config.get('alpha_energy'))
        self.alpha_reserve = float(self.config.get('alpha_reserve'))
        self.iteration_threshold = int(self.config.get('iteration_threshold'))

        self.init()
        self.grid_supplier = Generator()

        self.power_demand = []
        self.committed_reserves = []
        self.power_supply = []
        self.desired_reserves = []

    def init(self):
        self.iteration = 0
        self.price_energy = np.array([np.ones(self.T) * 40]).T
        self.price_reserved = np.array([np.ones(self.T) * 10]).T

    def get_exp_start_time(self):
        one_second = timedelta(seconds=1)
        if self.simulation:
            next_exp_time = datetime.now() + one_second
        else:
            now = datetime.now()
            offset = timedelta(seconds=3*Timer.sim_one_hr_in_sec)
            next_exp_time = now + offset
            if next_exp_time.day == now.day:
                next_exp_time = now + one_second
            else:
                _log.debug("{} did not run onstart because it's too late. Wait for next hour.".format(self.name))
                next_exp_time = next_exp_time.replace(hour=0, minute=0, second=0, microsecond=0)
        return next_exp_time

    def get_next_exp_time(self, cur_exp_time, cur_analysis_time):
        one_T_simulation = timedelta(seconds=self.T*self.simulation_one_hour_in_seconds)
        one_day = timedelta(days=1)
        one_minute = timedelta(minutes=1)

        cur_analysis_time = cur_analysis_time.replace(hour=0, minute=0, second=0, microsecond=0)
        if self.simulation:
            next_exp_time = cur_exp_time + one_T_simulation
        else:
            cur_exp_time = cur_exp_time.replace(hour=0, minute=0, second=0, microsecond=0)
            next_exp_time = cur_exp_time + one_day + one_minute

        next_analysis_time = cur_analysis_time + one_day + one_minute

        return next_exp_time, next_analysis_time

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        # Subscriptions
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=self.campus_demand_topic,
                                  callback=self.new_demand_signal)

        # Schedule to run 1st time if now is not too close to the end of day. Otherwise, schedule to run next day.
        next_exp_time = self.get_exp_start_time()
        next_analysis_time = next_exp_time
        if self.simulation:
            next_analysis_time = self.simulation_start_time

        _log.debug("{} schedule to run at exp_time: {} analysis_time: {}".format(self.name,
                                                                                 next_exp_time,
                                                                                 next_analysis_time))
        self.core.schedule(next_exp_time, self.schedule_run,
                           format_timestamp(next_exp_time),
                           format_timestamp(next_analysis_time))

    def schedule_run(self, cur_exp_time, cur_analysis_time):
        """
        Run when first start or run at beginning of day
        :return:
        """
        # Re-initialize each run
        self.init()

        # Schedule power from supplier and consumer
        self.schedule_power(start_of_cycle=True)

        # Schedule to run next day with start_of_cycle = True
        cur_exp_time = parser.parse(cur_exp_time)
        cur_analysis_time = parser.parse(cur_analysis_time)
        next_exp_time, next_analysis_time = self.get_next_exp_time(cur_exp_time, cur_analysis_time)
        self.core.schedule(next_exp_time, self.schedule_run,
                           format_timestamp(next_exp_time),
                           format_timestamp(next_analysis_time))

    def send_to_campus(self, converged=False, start_of_cycle=False):
        # Campus demand
        msg = {
            'ts': format_timestamp(Timer.get_cur_time()),
            'price': self.price_energy[:,-1].tolist(),
            'price_reserved': self.price_reserved[:,-1].tolist(),
            'converged': converged,
            'start_of_cycle': start_of_cycle
        }

        _log.info("City {} send to campus: {}".format(self.name, msg))
        self.vip.pubsub.publish(peer='pubsub',
                                topic=self.city_supply_topic,
                                message=msg)

        self.price_energy[:, -1]

    def schedule_power(self, start_of_cycle=False):
        # Grid supplier
        price_i = np.array([self.price_energy[:,-1]]).T
        reserve_i = np.array([self.price_reserved[:,-1]]).T
        self.power_supply, self.desired_reserves = \
            self.grid_supplier.generate_bid(self.T, price_i, reserve_i)

        self.send_to_campus(converged=False, start_of_cycle=start_of_cycle)

    def new_demand_signal(self, peer, sender, bus, topic, headers, message):
        _log.debug("At {}, {} receives new demand records: {}".format(Timer.get_cur_time(),
                                                                     self.name, message))
        self.power_demand = message['power_demand']
        self.committed_reserves = message['committed_reserves']

        if self.iteration < self.iteration_threshold:
            self.iteration += 1

            result = self.balance_market()
            # Start next iteration if balancing fails
            if not result:
                self.schedule_power(start_of_cycle=False)
            else:
                self.send_to_campus(converged=True, start_of_cycle=False)

    def balance_market(self):
        power_demand = np.array([self.power_demand]).T
        committed_reserves = np.array([self.committed_reserves]).T

        power_supply = self.power_supply
        desired_reserve = self.desired_reserves

        price_energy = np.array([self.price_energy[:, -1]]).T
        price_reserved = np.array([self.price_reserved[:, -1]]).T

        price_energy_new = price_energy - self.alpha_energy * (power_demand - power_supply)
        price_reserved_new = price_reserved - self.alpha_reserve * (committed_reserves - desired_reserve)

        self.price_energy = np.append(self.price_energy, price_energy_new, axis=1)
        self.price_reserved = np.append(self.price_reserved, price_reserved_new, axis=1)

        if np.linalg.norm(price_energy_new-price_energy) <= self.error_energy_threshold \
                and np.linalg.norm(price_reserved_new-price_reserved) <= self.error_reserve_threshold:
            return True

        return False


def main(argv=sys.argv):
    try:
        utils.vip_main(CityAgent)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
