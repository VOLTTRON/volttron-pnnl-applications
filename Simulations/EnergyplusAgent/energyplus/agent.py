# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}



import logging
import os
import socket
import subprocess
import sys
from datetime import datetime
from gevent import monkey, sleep
from inspect import getcallargs
import collections, sys, logging
from calendar import monthrange
import gevent

from math import modf
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.vip.agent import Agent, Core
from datetime import timedelta as td
from datetime import date


monkey.patch_socket()
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Core, RPC


utils.setup_logging()
log = logging.getLogger(__name__)
SUCCESS = 'SUCCESS'
FAILURE = 'FAILURE'

weekdays=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']

class PubSubAgent(Agent):
    def __init__(self, config_path, **kwargs):
        self.config = utils.load_config(config_path)
        self.inputs = collections.OrderedDict()
        self.outputs = collections.OrderedDict()
        self.month = None
        self.day = None
        self.hour = None
        self.minute = None
        self.second = None
        self.cosimulation_advance = None
        self.pause_until_message = None
        self.proceed = None
        self._now = None
        self.num_of_pub = None
        kwargs = self.update_kwargs_from_config(**kwargs)
        super(PubSubAgent, self).__init__(**kwargs)

    def update_kwargs_from_config(self, **kwargs):
        signature = getcallargs(super(PubSubAgent, self).__init__)
        for arg in signature:
            if 'properties' in self.config:
            #if self.config.has_key('properties'):
                properties = self.config.get('properties')
                if isinstance(properties, dict) and arg in properties:
                #if isinstance(properties, dict) and properties.has_key(arg):
                    kwargs[arg] = properties.get(arg)
        return kwargs

    @Core.receiver('onsetup')
    def setup(self, sender, **kwargs):
        if 'inputs' in self.config:
            self.inputs = self.config['inputs']
        if 'outputs' in self.config:
            outputs = self.config['outputs']
            self.outputs = self.create_ordered_output(outputs)
        if 'properties' in self.config and isinstance(self.config['properties'], dict):
            self.__dict__.update(self.config['properties'])
        self.cosimulation_advance = self.config.get('cosimulation_advance', None)
        self.pause_until_message = self.config.get("pause_until_message", None)
        self._now = datetime.utcnow()
        self.num_of_pub = 0
        self.month = None
        self.day = None
        self.hour = None
        self.minute = None

    @Core.receiver('onstart')
    def start(self, sender, **kwargs):
        self.subscribe()

    def create_ordered_output(self, output):
        last_key = None
        ordered_out = collections.OrderedDict()
        for key, value in output.items():
            if 'publish_last' not in value:
            #if not value.has_key('publish_last'):
                log.debug("Create output list: {} - {}".format(key, value))
                ordered_out[key] = value
            else:
                last_key = key
                last_value = value
        if last_key is not None:
            ordered_out[last_key] = last_value
        return ordered_out

    def input(self, *args):
        if len(args) == 0:
            return self.inputs
        return self.input_output(self.inputs, *args)

    def output(self, *args):
        if len(args) == 0:
            return self.outputs
        return self.input_output(self.outputs, *args)

    def input_output(self, dct, *args):
        if len(args) >= 1:
            key = args[0]
            if key in dct:
            #if dct.has_key(key):
                if len(args) >= 2:
                    field = args[1]
                    if len(args) >= 3:
                        dct.get(key)[field] = args[2]
                        return args[2]
                    return dct.get(key).get(field)
                return dct.get(key)
        return None

    def subscribe(self):
        for key, obj in self.input().items():
            if 'topic' in obj:
            #if obj.has_key('topic'):
                callback = self.on_match_topic
                topic = obj.get('topic')
                key_caps = 'onMatch' + key[0].upper() + key[1:]
                if 'callback' in obj:
                #if obj.has_key('callback'):
                    callbackstr = obj.get('callback')
                    if hasattr(self, callbackstr) and callable(getattr(self, callbackstr, None)):
                        callback = getattr(self, callbackstr)
                elif hasattr(self, key_caps) and callable(getattr(self, key_caps, None)):
                    callback = getattr(self, key_caps)
                log.info('subscribed to ' + topic)
                self.vip.pubsub.subscribe(peer='pubsub', prefix=topic, callback=callback)
        log.debug("Advance topic: {}".format(self.cosimulation_advance))
        if self.cosimulation_advance is not None:
            self.vip.pubsub.subscribe(peer='pubsub', prefix=self.cosimulation_advance, callback=self.advance_simulation)
        elif self.pause_until_message is not None:
            self.vip.pubsub.subscribe(peer='pubsub', prefix=self.pause_until_message, callback=self.release_pause)
        else:
            self.proceed = True

    def publish_all_outputs(self):
        # Publish messages
        self.publish(*self.output().values())

    def publish(self, *args):
        # Publish message
        self._now = self._now + td(minutes=1)
        num_days = (date(2017, int(self.month)+1, 1) - date(2017, int(self.month), 1)).days

        
        if self.month is None or self.day is None or self.minute is None or self.hour is None:
            _now = self._now
        else:
            if self.num_of_pub >= 1:
                if abs(self.minute - 60.0) < 0.5:
                    self.hour += 1.0
                    self.minute = 0.0
                if abs(self.hour - 24.0) < 0.5:
                    self.hour = 0.0
                    self.day += 1.0
                    if self.day > num_days:
                        self.day = 1
                        self.month = self.month+1
            else:
                self.hour = 0.0
                self.minute = 0.0
            second, minute = modf(self.minute)
            self.second = int(second * 60.0)
            self.minute = int(minute)
            date_string = '2017-' + str(self.month).replace('.0', '') + \
                          '-' + str(self.day).replace('.0', '') + ' ' + \
                          str(self.hour).replace('.0', '') + ':' + \
                          str(self.minute) + ':' + str(self.second)
            _now = datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
        _now = _now.isoformat(' ') + 'Z'
        log.info('Publish the builiding response for timetamp: {}.'.format(_now))

        headers = {headers_mod.DATE: _now, headers_mod.TIMESTAMP: _now}
        topics = collections.OrderedDict()
        for arg in args:
            obj = self.output(arg) if type(arg) == str else arg
            if 'topic' in obj and 'value' in obj:
            #if obj.has_key('topic') and obj.has_key('value'):
                topic = obj.get('topic', None)
                value = obj.get('value', None)
                field = obj.get('field', None)
                metadata = obj.get('meta', {})
                if topic is not None and value is not None:
                    if topic not in topics:
                    #if not topics.has_key(topic):
                        topics[topic] = {'values': None, 'fields': None}
                    if field is not None:
                        if topics[topic]['fields'] is None:
                            topics[topic]['fields'] = [{}, {}]
                        topics[topic]['fields'][0][field] = value
                        topics[topic]['fields'][1][field] = metadata
                    else:
                        if topics[topic]['values'] is None:
                            topics[topic]['values'] = []
                        topics[topic]['values'].append([value, metadata])
        for topic, obj in topics.items():
            if obj['values'] is not None:
                for value in obj['values']:
                    out = value
                    log.info('Sending: ' + topic + ' ' + str(out))
                    self.vip.pubsub.publish('pubsub', topic, headers, out).get()
            if obj['fields'] is not None:
                out = obj['fields']
                log.info('Sending: ' + topic + ' ' + str(out))
                while True:
                    try:
                        self.vip.pubsub.publish('pubsub', topic, headers, out).get()
                    except:
                        log.debug("Again ERROR: retrying publish")
                        gevent.sleep(0.1)
                        continue
                    break
            self.num_of_pub += 1

    def on_match_topic(self, peer, sender, bus, topic, headers, message):
        msg = message if type(message) == type([]) else [message]
        log.info('Received: ' + topic + ' ' + str(msg))
        self.update_topic(peer, sender, bus, topic, headers, msg)

    def update_topic(self, peer, sender, bus, topic, headers, message):
        objs = self.get_inputs_from_topic(topic)
        if objs is None:
            return
        for obj in objs:
            value = message[0]
            if type(value) is dict and 'field' in obj and obj.get('field') in value:
            #if type(value) is dict and obj.has_key('field') and value.has_key(obj.get('field')):
                value = value.get(obj.get('field'))
            obj['value'] = value
            obj['message'] = message[0]
            obj['message_meta'] = message[1]
            obj['last_update'] = headers.get(headers_mod.DATE, datetime.utcnow().isoformat(' ') + 'Z')
            self.on_update_topic(peer, sender, bus, topic, headers, message)

    def on_update_topic(self, peer, sender, bus, topic, headers, message):
        self.update_complete()

    def update_complete(self):
        self.on_update_complete()

    def on_update_complete(self):
        pass

    def clear_last_update(self):
        for obj in self.input().values():
            if 'topic' in obj:
            #if obj.has_key('topic'):
                obj['last_update'] = None

    def get_inputs_from_topic(self, topic):
        objs = []
        for obj in self.input().values():
            if obj.get('topic') == topic:
                objs.append(obj)
        topic = "/".join(["devices", topic, "all"])
        for obj in self.output().values():
            if obj.get('topic') == topic:
                objs.append(obj)
        if len(objs):
            return objs
        return None

    def find_best_match(self, topic):
        topic = topic.strip('/')
        device_name, point_name = topic.rsplit('/', 1)
        objs = self.get_inputs_from_topic(device_name)

        if objs is not None:
            for obj in objs:
                # we have matches to the <device topic>, so get the first one has a field matching <point name>
                if 'field' in obj and obj.get('field', None) == point_name:
                #if obj.has_key('field') and obj.get('field', None) == point_name:
                    return obj
        objs = self.get_inputs_from_topic(topic)
        if objs is not None and len(objs):  # we have exact matches to the topic
            return objs[0]
        return None


class SynchronizingPubSubAgent(PubSubAgent):
    def __init__(self, config_path, **kwargs):
        super(SynchronizingPubSubAgent, self).__init__(config_path, **kwargs)

    @Core.receiver('onstart')
    def start(self, sender, **kwargs):
        super(SynchronizingPubSubAgent, self).start(sender, **kwargs)
        self.update_complete()

    def update_complete(self):
        if self.all_topics_updated():
            self.clear_last_update()
            self.on_update_complete()

    def all_topics_updated(self):
        for obj in self.input().values():
            if 'topic' in obj:
            #if obj.has_key('topic'):
                if ('blocking' in obj and obj.get('blocking')) or 'blocking' not in obj:
                #if (obj.has_key('blocking') and obj.get('blocking')) or not obj.has_key('blocking'):
                    if 'last_update' in obj:
                    #if obj.has_key('last_update'):
                        if obj.get('last_update') is None:
                            return False
                    else:
                        return False
        return True

    def on_update_complete(self):
        self.publish_all_outputs()


class Event(object):
    @staticmethod
    def post(function, callback, *args):
        condition = True if len(args) == 0 else args[0]
        setattr(function.__self__, function.__name__, Event.__post(function, callback, condition))

    @staticmethod
    def __post(function, callback, condition):
        def __wrapper(*args, **kwargs):
            result = function(*args, **kwargs)
            if type(condition) == bool:
                istrue = condition
            else:
                istrue = condition()
            if istrue: callback()
            return result

        __wrapper.__name__ = function.__name__
        __wrapper.__self__ = function.__self__
        return __wrapper

    @staticmethod
    def pre(function, callback, *args):
        condition = True if len(args) == 0 else args[0]
        setattr(function.__self__, function.__name__, Event.__pre(function, callback, condition))

    @staticmethod
    def __pre(function, callback, condition):
        def __wrapper(*args, **kwargs):
            if type(condition) == bool:
                istrue = condition
            else:
                istrue = condition()
            if istrue: callback()
            result = function(*args, **kwargs)
            return result

        __wrapper.__name__ = function.__name__
        __wrapper.__self__ = function.__self__
        return __wrapper

class SocketServer():

    def __init__(self, **kwargs):
        self.sock = None
        self.size = 4096
        self.client = None
        self.sent = None
        self.rcvd = None
        self.host = "127.0.0.1"
        self.port = None

    def on_recv(self, msg):
        log.debug('Received %s' % msg)

    def run(self):
        self.listen()

    def connect(self):
        if self.host is None:
            self.host = socket.gethostname()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if self.port is None:
            self.sock.bind((self.host, 0))
            self.port = self.sock.getsockname()[1]
        else:
            self.sock.bind((self.host, self.port))
        log.debug('Bound to %r on %r' % (self.port, self.host))

    def send(self, msg):
        self.sent = msg
        if self.client is not None and self.sock is not None:
            try:
                self.client.send(self.sent)
            except Exception:
                log.error('We got an error trying to send a message.')

    def recv(self):
        if self.client is not None and self.sock is not None:
            try:
                msg = self.client.recv(self.size)
            except Exception:
                log.error('We got an error trying to read a message')
            return msg

    def start(self):
        log.debug('Starting socket server')
        self.run()

    def stop(self):
        if self.sock != None:
            self.sock.close()

    def listen(self):
        self.sock.listen(10)
        log.debug('server now listening')
        self.client, addr = self.sock.accept()
        log.debug('Connected with ' + addr[0] + ':' + str(addr[1]))
        while True:
            msg = self.recv()
            if msg:
                self.rcvd = msg
                self.on_recv(msg)


class EnergyPlusAgent(SynchronizingPubSubAgent):
    def __init__(self, config_path, **kwargs):
        super(EnergyPlusAgent, self).__init__(config_path, **kwargs)
        self.version = 8.4
        self.bcvtb_home = '.'
        self.model = None
        self.customizedOutT = 0
        self.weather = None
        self.socketFile = None
        self.variableFile = None
        self.time = 0
        self.vers = 2
        self.flag = 0
        self.sent = None
        self.rcvd = None
        self.socket_server = None
        self.simulation = None
        self.step = None
        self.eplus_inputs = 0
        self.eplus_outputs = 0
        self.cosim_sync_counter = 0
        self.tns_actuate = None
        self.rt_periodic = None
        self.time_scale = 1.0
        self.passtime = False
        self.real_time_flag = False
        self.currenthour=datetime.now().hour
        self.currentday=datetime.now().day
        self.currentmonth=datetime.now().month
        self.length=1
        self.maxday=monthrange(2012, self.currentmonth)[1]

        if not self.config:
            self.exit('No configuration found.')
        self.cwd = os.getcwd()

    @Core.receiver('onsetup')
    def setup(self, sender, **kwargs):
        super(EnergyPlusAgent, self).setup(sender, **kwargs)

    @Core.receiver('onstart')
    def start(self, sender, **kwargs):
        self.subscribe()
        self.clear_last_update()
        self.start_socket_server()
        self.start_simulation()

    def start_socket_server(self):
        self.socket_server = SocketServer()
        self.socket_server.size = self.size
        self.socket_server.on_recv = self.recv_eplus_msg
        self.socket_server.connect()
        self.core.spawn(self.socket_server.start)

    def start_simulation(self):
        if not self.model:
            self.exit('No model specified.')
        if not self.weather:
            self.exit('No weather specified.')
        model_path = self.model
        if model_path[0] == '~':
            model_path = os.path.expanduser(model_path)
        if model_path[0] != '/':
            model_path = os.path.join(self.cwd, model_path)
        weather_path = self.weather
        if weather_path[0] == '~':
            weather_path = os.path.expanduser(weather_path)
        if weather_path[0] != '/':
            weather_path = os.path.join(self.cwd, weather_path)
        model_dir = os.path.dirname(model_path)
        bcvtb_dir = self.bcvtb_home
        if bcvtb_dir[0] == '~':
            bcvtb_dir = os.path.expanduser(bcvtb_dir)
        if bcvtb_dir[0] != '/':
            bcvtb_dir = os.path.join(self.cwd, bcvtb_dir)
        log.debug('Working in %r', model_dir)
        self.write_port_file(os.path.join(model_dir, 'socket.cfg'))
        self.write_variable_file(os.path.join(model_dir, 'variables.cfg'))
        if self.version >= 8.4:
            cmd_str = "cd %s; export BCVTB_HOME=%s; energyplus -w %s -r %s" % (
            model_dir, bcvtb_dir, weather_path, model_path)
        else:
            cmd_str = "export BCVTB_HOME=%s; runenergyplus %s %s" % (bcvtb_dir, model_path, weather_path)
        log.debug('Running: %s', cmd_str)
        f = open(model_path, 'r')
        lines = f.readlines()
        f.close()
        if self.currentday+self.length>self.maxday:
                endday=self.currentday+self.length-self.maxday
                endmonth=self.currentmonth+1
        else:
                endday=self.currentday+self.length
                endmonth=self.currentmonth
        for i in range(len(lines)):
            if lines[i].lower().find('runperiod,') != -1:
               if not self.real_time_flag:
                  lines[i + 2] = '    ' + str(self.startmonth) + ',                       !- Begin Month' + '\n'
                  lines[i + 3] = '    ' + str(self.startday) + ',                       !- Begin Day of Month' + '\n'
                  lines[i + 4] = '    ' + str(self.endmonth) + ',                      !- End Month' + '\n'
                  lines[i + 5] = '    ' + str(self.endday) + ',                      !- End Day of Month' + '\n'
                  lines[i + 6] = '    ' +weekdays[int(datetime(2017,int(self.startmonth),int(self.startday)).weekday())]+',                  !- Day of Week for Start Day' + '\n'
               else:
                  lines[i + 2] = '    ' + str(self.currentmonth) + ',                       !- Begin Month' + '\n'
                  lines[i + 3] = '    ' + str(self.currentday) + ',                       !- Begin Day of Month' + '\n'
                  lines[i + 4] = '    ' + str(endmonth) + ',                      !- End Month' + '\n'
                  lines[i + 5] = '    ' + str(endday) + ',                      !- End Day of Month' + '\n'
                  lines[i + 6] = '    ' +weekdays[int(datetime(2017,int(self.currentmonth),int(self.currentday)).weekday())]+',                  !- Day of Week for Start Day' + '\n'
        for i in range(len(lines)):
            if lines[i].lower().find('timestep,') != -1 and lines[i].lower().find('update frequency') == -1:
                if lines[i].lower().find(';') != -1:
                    lines[i] = '  Timestep,' + str(self.timestep) + ';' + '\n'
                else:
                    lines[i + 1] = '  ' + str(self.timestep) + ';' + '\n'
        if self.customizedOutT>0:
              lines.append('ExternalInterface:Actuator,')+ '\n'
              lines.append('    outT,     !- Name')+ '\n'
              lines.append('    Environment,  !- Actuated Component Unique Name')+ '\n'
              lines.append('    Weather Data,  !- Actuated Component Type')+ '\n'
              lines.append('    Outdoor Dry Bulb;          !- Actuated Component Control Type')+ '\n'
        f = open(model_path, 'w')

        for i in range(len(lines)):
            f.writelines(lines[i])
        f.close()
        self.simulation = subprocess.Popen(cmd_str, shell=True)

    def send_eplus_msg(self):
        if self.socket_server:
            args = self.input()
            msg = '%r %r %r 0 0 %r' % (self.vers, self.flag, self.eplus_inputs, self.time)
            for obj in args.values():
                if obj.get('name', None) and obj.get('type', None):
                    msg = msg + ' ' + str(obj.get('value'))
            self.sent = msg + '\n'
            log.info('Sending message to EnergyPlus: ' + msg)
            self.sent = self.sent.encode()
            self.socket_server.send(self.sent)

    def recv_eplus_msg(self, msg):
        self.rcvd = msg
        self.parse_eplus_msg(msg)
        if self.sim_flag != '1':
            self.publish_all_outputs()
        log.debug("Cosim realtime: {} -- periodic {} -- proceed {}".format(self.realtime, self.rt_periodic, self.proceed))
        if self.realtime and self.rt_periodic is None:
            while not self.proceed:
                gevent.sleep(0.25)
            timestep = 60. / (self.timestep*self.time_scale)*60.
            self.rt_periodic = self.core.periodic(timestep, self.run_periodic, wait=timestep)
        if self.cosimulation_sync:
            self.check_advance()

    def check_advance(self):
        if self.realtime:
            return
        timestep = int(60/self.timestep)
        #if self.operation>0:
        if not self.real_time_flag:
           self.cosim_sync_counter += timestep
           if self.cosim_sync_counter < self.co_sim_timestep:
                  self.advance_simulation(None, None, None, None, None, None)
           else:
                  self.cosim_sync_counter = 0
                  self.vip.pubsub.publish('pubsub', self.tns_actuate, headers={}, message={}).get(timeout=10)
        else:
           if self.hour>self.currenthour or self.passtime:
              self.passtime=True
              self.cosim_sync_counter += timestep
              if self.cosim_sync_counter < self.co_sim_timestep:
                  self.advance_simulation(None, None, None, None, None, None)
              else:
                  self.cosim_sync_counter = 0
                  self.vip.pubsub.publish('pubsub', self.tns_actuate, headers={}, message={}).get(timeout=10)
           else:
                  self.advance_simulation(None, None, None, None, None, None)
        #else:
        #    self.advance_simulation(None, None, None, None, None, None)
        return

    def run_periodic(self):
        self.advance_simulation(None, None, None, None, None, None)
        self.send_eplus_msg()

    def parse_eplus_msg(self, msg):
        msg = msg.decode("utf-8") 
        msg = msg.rstrip()
        arry = msg.split()
        arry = [float(item) for item in arry]
        log.info('Received message from EnergyPlus: ' + str(arry))
        slot = 6
        self.sim_flag = arry[1]
        output = self.output()
        log.info('Outputs: ' + str(output))
        input = self.input()

        if self.sim_flag != 0.0:
            log.debug("FLAG: {} - {}".format(self.sim_flag, type(self.sim_flag)))
            if self.sim_flag == '1':
                self.exit('Simulation reached end: ' + self.sim_flag)
            elif self.sim_flag == '-1':
                self.exit('Simulation stopped with unspecified error: ' + self.sim_flag)
            elif self.sim_flag == '-10':
                self.exit('Simulation stopped with error during initialization: ' + self.sim_flag)
            elif self.sim_flag == '-20':
                self.exit('Simulation stopped with error during time integration: ' + self.sim_flag)
        elif arry[2] < self.eplus_outputs and len(arry) < self.eplus_outputs + 6:
            self.exit('Got message with ' + arry[2] + ' inputs. Expecting ' + str(self.eplus_outputs) + '.')
        else:
            if float(arry[5]):
                self.time = float(arry[5])
            for key in input:
                if self.input(key, 'name') and self.input(key, 'dynamic_default'):
                    slot = 6
                    for key2 in output:
                        if self.output(key2, 'default'):
                            if self.output(key2, 'default').lower().find(self.input(key, 'name').lower()) != -1:
                                self.input(key, 'default', float(arry[slot]))
                                log.info('Reset')
                        slot += 1
            slot = 6
            for key in output:
                if self.output(key, 'name') and self.output(key, 'type'):
                    try:
                        self.output(key, 'value', float(arry[slot]))
                    except:
                        print(slot)
                        self.exit('Unable to convert received value to double.')
                    if self.output(key, 'type').lower().find('currentmonthv') != -1:
                        self.month = float(arry[slot])
                        print(('month ' + str(self.month)))
                    elif self.output(key, 'type').lower().find('currentdayofmonthv') != -1:
                        self.day = float(arry[slot])
                        print(('day ' + str(self.day)))
                    elif self.output(key, 'type').lower().find('currenthourv') != -1:
                        self.hour = float(arry[slot])
                        print(('hour ' + str(self.hour)))
                    elif self.output(key, 'type').lower().find('currentminutev') != -1:
                        self.minute = float(arry[slot])
                        print(('minute ' + str(self.minute)))
                    elif self.output(key, 'field'):  
                           if self.output(key, 'field').lower().find('operation') != -1:
                                 self.operation = float(arry[slot])
                                 print(('operation (1:on, 0: off) ' + str(self.operation)))
                    slot += 1

    def exit(self, msg):
        self.stop()
        log.error(msg)

    def stop(self):
        if self.socket_server:
            self.socket_server.stop()
            self.socket_server = None

    def write_port_file(self, path):
        fh = open(path, "w+")
        fh.write('<?xml version="1.0" encoding="ISO-8859-1"?>\n')
        fh.write('<BCVTB-client>\n')
        fh.write('  <ipc>\n')
        fh.write('    <socket port="%r" hostname="%s"/>\n' % (self.socket_server.port, self.socket_server.host))
        fh.write('  </ipc>\n')
        fh.write('</BCVTB-client>')
        fh.close()

    def write_variable_file(self, path):
        fh = open(path, "w+")
        fh.write('<?xml version="1.0" encoding="ISO-8859-1"?>\n')
        fh.write('<!DOCTYPE BCVTB-variables SYSTEM "variables.dtd">\n')
        fh.write('<BCVTB-variables>\n')
        for obj in self.output().values():
            if 'name' in obj and 'type' in obj:
            #if obj.has_key('name') and obj.has_key('type'):
                self.eplus_outputs = self.eplus_outputs + 1
                fh.write('  <variable source="EnergyPlus">\n')
                fh.write('    <EnergyPlus name="%s" type="%s"/>\n' % (obj.get('name'), obj.get('type')))
                fh.write('  </variable>\n')
        for obj in self.input().values():
            if 'name' in obj and 'type' in obj:
            #if obj.has_key('name') and obj.has_key('type'):
                self.eplus_inputs = self.eplus_inputs + 1
                fh.write('  <variable source="Ptolemy">\n')
                fh.write('    <EnergyPlus %s="%s"/>\n' % (obj.get('type'), obj.get('name')))
                fh.write('  </variable>\n')
        fh.write('</BCVTB-variables>\n')
        fh.close()

    @RPC.export
    def request_new_schedule(self, requester_id, task_id, priority, requests):
        """RPC method

        Requests one or more blocks on time on one or more device.
        In this agent, this does nothing!

        :param requester_id: Requester name.
        :param task_id: Task name.
        :param priority: Priority of the task. Must be either HIGH, LOW, or LOW_PREEMPT
        :param requests: A list of time slot requests

        :type requester_id: str
        :type task_id: str
        :type priority: str
        :type request: list
        :returns: Request result
        :rtype: dict

        """
        log.debug(requester_id + " requests new schedule " + task_id + " " + str(requests))
        result = {'result': SUCCESS,
                  'data': {},
                  'info': ''}
        return result

    @RPC.export
    def request_cancel_schedule(self, requester_id, task_id):
        """RPC method

        Requests the cancelation of the specified task id.
        In this agent, this does nothing!

        :param requester_id: Requester name.
        :param task_id: Task name.

        :type requester_id: str
        :type task_id: str
        :returns: Request result
        :rtype: dict

        """
        log.debug(requester_id + " canceled " + task_id)
        result = {'result': SUCCESS,
                  'data': {},
                  'info': ''}
        return result

    @RPC.export
    def get_point(self, topic, **kwargs):
        """RPC method

        Gets the value of a specific point on a device_name.
        Does not require the device_name be scheduled.

        :param topic: The topic of the point to grab in the
                      format <device_name topic>/<point name>
        :param **kwargs: These get dropped on the floor
        :type topic: str
        :returns: point value
        :rtype: any base python type

        """
        obj = self.find_best_match(topic)
        if obj is not None:  # we have an exact match to the  <device_name topic>/<point name>, so return the first value
            value = obj.get('value', None)
            if value is None:
                value = obj.get('default', None)
            return value
        return None

    @RPC.export
    def set_point(self, requester_id, topic, value, **kwargs):
        """RPC method

        Sets the value of a specific point on a device.
        Does not require the device be scheduled.

        :param requester_id: Identifier given when requesting schedule.
        :param topic: The topic of the point to set in the
                      format <device topic>/<point name>
        :param value: Value to set point to.
        :param **kwargs: These get dropped on the floor
        :type topic: str
        :type requester_id: str
        :type value: any basic python type
        :returns: value point was actually set to.
        :rtype: any base python type

        """
        topic = topic.strip('/')
        external = True
        if value is None:
            result = self.revert_point(requester_id, topic)
        else:
            result = self.update_topic_rpc(requester_id, topic, value, external)
            log.debug("Writing: {topic} : {value} {result}".format(topic=topic, value=value, result=result))
        if result == SUCCESS:
            return value
        else:
            raise RuntimeError("Failed to set value: " + result)

    @RPC.export
    def revert_point(self, requester_id, topic, **kwargs):
        """RPC method

        Reverts the value of a specific point on a device to a default state.
        Does not require the device be scheduled.

        :param requester_id: Identifier given when requesting schedule.
        :param topic: The topic of the point to revert in the
                      format <device topic>/<point name>
        :param **kwargs: These get dropped on the floor
        :type topic: str
        :type requester_id: str

        """
        obj = self.find_best_match(topic)
        if obj and 'default' in obj:
        #if obj and obj.has_key('default'):
            value = obj.get('default')
            log.debug("Reverting topic " + topic + " to " + str(value))
            external = False
            result = self.update_topic_rpc(requester_id, topic, value, external)
        else:
            result = FAILURE
            log.warning("Unable to revert topic. No topic match or default defined!")
        return result

    @RPC.export
    def revert_device(self, requester_id, device_name, **kwargs):
        """RPC method

        Reverts all points on a device to a default state.
        Does not require the device be scheduled.

        :param requester_id: Identifier given when requesting schedule.
        :param topic: The topic of the device to revert (without a point!)
        :param **kwargs: These get dropped on the floor
        :type topic: str
        :type requester_id: str

        """
        device_name = device_name.strip('/')
        objs = self.get_inputs_from_topic(device_name)  # we will assume that the topic is only the <device topic> and revert all matches at this level!
        if objs is not None:
            for obj in objs:
                point_name = obj.get('field', None)
                topic = device_name + "/" + point_name if point_name else device_name
                external = False
                if 'default' in obj:
                #if obj.has_key('default'):
                    value = obj.get('default')
                    log.debug("Reverting " + topic + " to " + str(value))
                    self.update_topic_rpc(requester_id, topic, value, external)
                else:
                    log.warning("Unable to revert " + topic + ". No default defined!")

    def update_topic_rpc(self, requester_id, topic, value, external):
        obj = self.find_best_match(topic)
        if obj is not None:
            obj['value'] = value
            obj['external'] = external
            obj['last_update'] = datetime.utcnow().isoformat(' ') + 'Z'
            if not self.realtime:
                self.on_update_topic_rpc(requester_id, topic, value)
            return SUCCESS
        return FAILURE

    def advance_simulation(self, peer, sender, bus, topic, headers, message):
        log.info('Advancing simulation.')
        for obj in self.input().values():
            set_topic = obj['topic'] + '/' + obj['field']
            if 'external' in obj and obj['external']:
            #if obj.has_key('external') and obj['external']:
                external = True
                value = obj['value'] if 'value' in obj else obj['default']
                #value = obj['value'] if obj.has_key('value') else obj['default']
            else:
                external = False
                value = obj['default']
            self.update_topic_rpc(sender, set_topic, value, external)
        return

    def release_pause(self, peer, sender, bus, topic, headers, message):
        self.proceed = True
        return

    def on_update_topic_rpc(self, requester_id, topic, value):
        self.update_complete()

    def on_update_complete(self):
        self.send_eplus_msg()


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(EnergyPlusAgent)
    except Exception as e:
        log.exception(e)


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
