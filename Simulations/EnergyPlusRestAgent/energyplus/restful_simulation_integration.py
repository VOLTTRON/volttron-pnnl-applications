# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

import os
import logging
from gevent import monkey, sleep
import requests
import json
import weakref
import socket
import subprocess
from datetime import datetime, timedelta
from calendar import monthrange
from volttron.platform.agent.base_simulation_integration.base_sim_integration import BaseSimIntegration

monkey.patch_socket()
_log = logging.getLogger(__name__)
__version__ = '1.0'

HAS_ENERGYPLUS = True


class EnergyPlusSimIntegration(BaseSimIntegration):
    """
    The class is responsible for integration with EnergyPlus simulation
    """

    def __init__(self, config, pubsub, core):
        super(EnergyPlusSimIntegration, self).__init__(config)
        self.pubsub = weakref.ref(pubsub)
        self.core = weakref.ref(core)
        self.current_time = 0
        self.inputs = {}
        self.outputs = {}
        self.current_values = {}
        self.url = config.get("url", 'http://127.0.0.1:5500')
        self.model = None
        self.time = 0
        self.sent = None
        self.rcvd = None
        self.simulation = None
        self.step = None
        self.eplus_inputs = 0
        self.eplus_outputs = 0
        self.cosim_sync_counter = 0
        self.time_scale = 1.0
        self.passtime = False
        self.size = None
        self.real_time_flag = False
        self.currenthour = datetime.now().hour
        self.currentday = datetime.now().day
        self.currentmonth = datetime.now().month
        self.length = 1
        self.maxday = monthrange(2012, self.currentmonth)[1]
        self.callback = None
        self.month = None
        self.year = None
        self.day = None
        self.minute = None
        self.operation = None
        self.timestep = None
        self.cosimulation_sync = None
        self.real_time_periodic = None
        self.co_sim_timestep = None
        self.startmonth = None
        self.startday = None
        self.endmonth = None
        self.endday = None
        self.absolute_start_date = None
        self.simulation_start = None
        self.simulation_end = None
        self.current_sim_time = None

    def register_inputs(self, config=None, callback=None, **kwargs):
        """
        Store input and output configurations
        Save the user agent callback
        :return:
        """
        self.inputs = self.config.get('inputs', {})
        self.outputs = self.config.get('outputs', {})
        if 'properties' in self.config and isinstance(self.config['properties'], dict):
            self.__dict__.update(self.config['properties'])
        _log.debug("REALTIME PERIODIC: {}".format(self.real_time_periodic))
        self.setup_time()
        self.callback = callback

    def setup_time(self):
        if self.year is None:
            self.year = datetime.now().year
        self.absolute_start_date = datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0, year=self.year)
        start = datetime.now().replace(month=self.startmonth, day=self.startday, hour=0, minute=0, second=0, microsecond=0, year=self.year)
        self.current_sim_time = start
        end = datetime.now().replace(month=self.endmonth, day=self.endday, hour=23, minute=59, second=0, microsecond=0, year=self.year)
        self.simulation_start = (start - self.absolute_start_date).days * 86400
        self.simulation_end = (end - self.absolute_start_date).days * 86400

    def calculate_current_simtime(self, sim_time):
        return self.absolute_start_date + timedelta(seconds=sim_time)

    def start_simulation(self, *args, **kwargs):
        """
        Start EnergyPlus simulation
        :return:
        """
        inputs = requests.get('{0}/inputs'.format(self.url)).json()
        measurements = requests.get('{0}/measurements'.format(self.url)).json()
        self.validate_outputs(measurements)
        _log.debug("EPLUS outputs: {}".format(measurements))
        self.validate_inputs(inputs)
        _log.debug("EPLUS inputs: {}".format(inputs))
        res = requests.put('{0}/step'.format(self.url), data={"step": self.timestep})
        y = requests.post('{0}/advance'.format(self.url), json=json.dumps({})).json()
        _log.debug("EPLUS reset simulation start: {} -- end: {}".format(self.simulation_start, self.simulation_end))
        res = requests.put('{0}/reset'.format(self.url), data={'start_time': self.simulation_start, 'end_time': self.simulation_end})
        self.send_eplus_msg(init=True)

    def publish_all_to_simulation(self, inputs):
        self.inputs = inputs
        self.send_eplus_msg()

    def send_eplus_msg(self, init=False):
        """
        Send inputs to EnergyPlus
        """
        _log.debug("send_eplus_msg ")
        control = {}
        args = self.input()
        _log.debug("INPUTS: {}".format(self.inputs))
        if not init:
            for point, info in self.inputs.items():
                if info.get('value') is not None:
                    control[point] = info["value"]
                    _log.debug("CONTROL: {} --- {}".format(point, info["value"]))
        y = requests.post('{0}/advance'.format(self.url), json=json.dumps(control)).json()
        self.recv_eplus_msg(y)
        _log.info('Sending message to EnergyPlus: {}'.format(control))
        _log.info('Sending2 message from EnergyPlus: {}'.format(y))
    
    def recv_eplus_msg(self, msg):
        """
        Receive outputs from EnergyPlus, parse the messages and hand it over
        to user callback
        """
        self.rcvd = msg
        self.parse_eplus_msg(msg)
        # Call Agent callback to do whatever with the message
        if self.callback is not None:
            self.callback()
    
    def parse_eplus_msg(self, measurements):
        """
        Parse EnergyPlus message to update output values and
        simulation datetime
        """
        try:
            sim_time = measurements["time"]
            self.current_sim_time = self.calculate_current_simtime(sim_time)
        except KeyError:
            _log.debug("Missing time from measurments!")
            self.current_sim_time += timedelta(seconds=self.timestep)

        for name, output in self.outputs.items():
            field_value = output.get('field', None)
            _log.debug("Sending3 message {}: {} {}".format(name, measurements[name], field_value))
            if field_value is not None:
                try:
                    output['value'] = measurements[name]
                except:
                    _log.debug("Problem parsing meaasurement from E+!")

    def publish_to_simulation(self, topic, message, **kwargs):
        """
        Publish message on EnergyPlus simulation
        :param topic: EnergyPlus input field
        :param message: message
        :return:
        """
        pass

    def make_time_request(self, time_request=None, **kwargs):
        """
        Cannot request time with energyplus
        :param time_request:
        :return:
        """
        pass

    def pause_simulation(self, timeout=None, **kwargs):
        pass

    def resume_simulation(self, *args, **kwargs):
        pass

    def input(self):
        return self.inputs

    def validate_outputs(self, measurements):
        from_sim = set(measurements)
        configured = set(self.outputs.keys())
        if from_sim != configured:
            _log.warning("Configured outputs do not match the measurements form the simulation!")
            if len(from_sim) > len(configured):
                _log.warning("Configuration is missing parameters! : {}".format(from_sim-configured))
            if len(from_sim) > len(configured):
                _log.warning("Configuration has more measurements than simulation! : {}".format(configured-from_sim))
            #self.core.stop()

    def validate_inputs(self, inputs):
        from_sim = set(inputs)
        configured = set(self.inputs.keys())
        if from_sim != configured:
            _log.warning("Configured inputs do not match the measurements form the simulation!")
            if len(from_sim) > len(configured):
                _log.warning("Configuration is missing parameters! : {}".format(from_sim - configured))
            if len(from_sim) > len(configured):
                _log.warning("Configuration has more inputs than simulation! : {}".format(configured - from_sim))
            #self.core.stop()
