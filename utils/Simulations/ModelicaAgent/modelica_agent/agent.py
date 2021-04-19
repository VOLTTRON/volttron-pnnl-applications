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
# 'AS IS' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
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
import socket
import sys
import json
from collections import defaultdict
from gevent import monkey, sleep
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.scheduling import periodic

monkey.patch_socket()
utils.setup_logging()
log = logging.getLogger(__name__)
SUCCESS = 'SUCCESS'
FAILURE = 'FAILURE'


class SocketServer:
    """
    Socket server class that facilitates communication with Modelica.
    """
    def __init__(self, port, host):
        """
        Contstructor for SocketServer.
        :param port: int; port to listen.
        :param host: str; IP address, defaults to '127.0.0.1'
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Bind socket server to IP and Port
        self.sock.bind((host, port))
        self.client = None
        self.received_data = None
        self.size = 4096
        log.debug('Bound to %s on %s' % (port, host))

    def run(self):
        """
        Calls listen method.
        :return:
        """
        self.listen()

    def listen(self):
        """
        Execution loop for SocketServer.
        Facilitates transmission of data from Modelica
        :return:
        """
        self.sock.listen(10)
        log.debug('server now listening')
        while True:
            # Reopen connection to receive communication as the
            # connection is closed by SocketServer after each transmittal.
            self.client, addr = self.sock.accept()
            log.debug('Connected with %s:%s', addr[0], addr[1])
            data = self.receive_data()
            # Python3 will send the data as a byte not a string
            data = data.decode('utf-8')
            log.debug('Modelica data %s', data)
            if data:
                data = json.loads(data)
                self.received_data = data
                self.on_receive_data(data)

    def receive_data(self):
        """
        Client resource receives data payload from Modelica.
        :return: data where input data is a list output data is a
        dictionary.
        """
        if self.client is not None and self.sock is not None:
            try:
                data = self.client.recv(self.size)
            except Exception:
                log.error('We got an error trying to read a message')
                data = None
            return data

    def on_receive_data(self, data):
        """
        on_recieve_data stub.
        :param data: data payload from Modelica.
        :return:
        """
        log.debug('Received %s', data)

    def stop(self):
        """
        On stop close the socket.
        :return:
        """
        if self.sock is not None:
            self.sock.close()


class ModelicaAgent(Agent):
    """
    Modelica agent allows co-simulation with Modelica and
    Facilitates data exchange between VOLLTRON and Modelica model.
    """
    def __init__(self, config_path, **kwargs):
        """
        Constructor for ModelicaAgent
        :param config_path: str; path to config file
        :param kwargs:
        """
        super().__init__(**kwargs)
        config = utils.load_config(config_path)
        # Set IP and port that SocketServer will bind
        self.remote_ip = config.get('remote_ip', '127.0.0.1')
        self.remote_port = config.get('remote_port', 8888)
        self.socket_server = None
        # Read outputs dictionary and inputs dictionary
        outputs = config.get('outputs', {})
        inputs = config.get('inputs', {})
        self.advance_topic = config.get("advance_simulation_topic")

        # Initialize input related parameters.
        self.control_map = {}
        self.control_topic_map = {}
        self.controls_list_master = set()
        self.controls_list = []
        self.control_proceed = set()
        self.current_control = None
        self.time_step_interval = config.get('timestep_interval', 30)
        self.time_step = 1

        # Initialize output related parameters.
        self.data_map = {}
        self.data_map_master = None
        self.output_data = defaultdict(list)
        self.output_map = None

        self.create_control_map(inputs)
        self.create_output_map(outputs)
        model = config.get("model")
        run_time = config.get("model_runtime", 500)
        result_file = config.get('result_file', 'result')
        mos_file_path = config.get('mos_file_path', 'run.mos')
        self.create_mos_file(model, run_time, result_file, mos_file_path)
        self.run_time = run_time

    def create_mos_file(self, model, run_time, result_file, mos_file_path):
        write = 'simulateModel("{}", stopTime={}, method="dassl", resultFile="{}");\n'.format(model, run_time, result_file)
        write_list = [write, "\n", "exit();"]
        _file = open(mos_file_path, "w")
        _file.writelines(write_list)
        _file.close()

    def create_output_map(self, outputs):
        """
        Create the data_map necessary for tracking if all outputs
        from Modelica are received for a timestep.
        :param outputs:
        :return:
        """
        # data_map contains topic, field (aka volttron point name),
        # and meta data associated with each unique Modelica point name.
        self.data_map = outputs
        for name, info in outputs.items():
            topic = info['topic']
            self.output_data[topic] = [{}, {}]
        # Modelica sends the measurements one at a time.  When
        # the agent receives a measurement it removes the point from the
        # data_map but data_map_master is never manipulated after it is created
        self.data_map_master = dict(self.data_map)
        log.debug('data %s', self.data_map)

    def create_control_map(self, inputs):
        """
        Create the control_topic_map, control_map, and cotnrols_list.
        control_topic_map - volttron topic to Modelica point name map
        control_map - Modelica point name to current input to Modelica
        controls_list - list of all inputs.  Empty when all setpoints have been
        received
        information.
        :param inputs: dictionary where key is Modelica point name and value
        is input information.
        :return:
        """
        for name, info in inputs.items():
            topic = '/'.join([info['topic'], info['field']])
            self.control_topic_map[topic] = name
            self.control_map[name] = {
                'value': 0,
                'nextSampleTime': 1,
                'enable': False
            }
            self.controls_list_master = set(self.control_map.keys())
            self.controls_list = list(self.controls_list_master)
            log.debug('Control map %s', self.control_map)

    @Core.receiver('onstart')
    def start(self, sender, **kwargs):
        """
        ON agent start call function to instantiate the socket server.
        :param sender: not used
        :param kwargs: not used
        :return:
        """
        if self.advance_topic is not None:
            if isinstance(self.advance_topic, str) and self.advance_topic:
                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=self.advance_topic,
                                          callback=self.advance_simulation)
        self.start_socket_server()

    def start_socket_server(self):
        """
        Instantiate the SocketServer to the configured IP
        and port.  Spawn an this as a gevent loop
        executing the run method of the SocketServer.
        :return:
        """
        self.socket_server = SocketServer(port=self.remote_port,
                                          host=self.remote_ip)
        self.socket_server.on_receive_data = self.receive_modelica_data
        self.core.spawn(self.socket_server.run)

    def receive_modelica_data(self, data):
        """
        Receive a data payload from Modelica.
        A data payload dictionary is output data for to publish to message bus.
        A data payload lis indicates a control signal can be sent to
        Modelica [point(str), time(int)].
        :param data: data payload from Modelica.
        :return:
        """
        self.data = data
        log.debug('Modelica Agent receive data %s - %s', data, type(data))
        if isinstance(data, dict):
            self.publish_modelica_data(data)
        else:
            self.current_control = data
            name = data[0]
            self.control_proceed.add(name)
            # If the controls_list is empty then all
            # set points have been received.
            if not self.controls_list:
                # Since Modelica sends each control list one at a time
                # and expects a subsequent answer in the correct order
                # an additional list of points is created to know when
                # all messages have been sent to Modelica and it is time
                # to reinitialize the controls_list.
                self.send_control_signal(self.current_control)
                if self.control_proceed == self.controls_list_master:
                    self.reinit_control_lists()

    def reinit_control_lists(self):
        """
        Reinitialize the controls_list for tracking if all setpoints have
        been received.
        :return:
        """
        log.debug('Reinitialize controls list')
        self.controls_list = list(self.controls_list_master)
        self.control_proceed = set()
        self.current_control = None

    def send_control_signal(self, control):
        """
        Send the control signal to Modelica.
        :param control:
        :return:
        """
        msg = {}
        name = control[0]
        _time = control[1]
        # This is not required but for simplicity
        # this agent uses a uniform value for the
        # nextSampleTime parameter for all inputs to Modelica.
        next_sample_time = _time + self.time_step_interval
        if next_sample_time > self.run_time:
            next_sample_time = self.run_time
        self.control_map[name]['nextSampleTime'] = next_sample_time
        msg[name] = self.control_map[name]
        msg = json.dumps(msg)
        msg = msg + '\0'
        log.debug('Send control input to Modelica: %s', msg)
        # For Python3 this must be byte encoded.
        # For Python2 a string would be used.
        msg = msg.encode()
        # Send the input to Modelica via the SocketServer.
        self.socket_server.client.send(msg)

    def publish_modelica_data(self, data):
        """
        This function publishes the Modelica output data once all
        outputs for a timestep have been received from Modelica.
        Uses an all publish per device.  This means that outputs
        can be configured with the same topic and will be published
        as topic/all consistent with the MasterDriver topic/data format.
        :param data: dictionary where key is Modelica point name and value is
        data information.
        :return:
        """
        log.debug('Modelica publish method %s', data)
        self.construct_data_payload(data)
        for key in data:
            self.data_map.pop(key)
        # data_map will be empty when all data for a timestep
        # is received.
        if self.data_map:
            return
        # Once all data is received iterate over the output_data
        # built in construct_data_payload  The key is the device publish
        # topic and the value is the data payload in the same format that the
        # MasterDriverAgent uses.
        for topic, value in self.output_data.items():
            self.data_map = dict(self.data_map_master)
            headers = {'Timestep': self.time_step}
            publish_topic = "/".join([topic, "all"])
            log.debug('Publish - topic %s ----- payload %s', topic, value)
            self.vip.pubsub.publish('pubsub',
                                    publish_topic,
                                    headers=headers,
                                    message=value)
        if self.time_step >= self.run_time:
            log.debug("Simulation has finished!")
            self.exit()

    def construct_data_payload(self, data):
        """
        This function uses the data_map information
        to assemble the data payload for each device.
        :param data:
        :return:
        """
        for key, payload in data.items():
            data_map = self.data_map_master[key]
            topic = data_map['topic']
            name = data_map['field']
            value = payload['value']
            meta = data_map['meta']
            self.time_step = payload['time']
            self.output_data[topic][0].update({name: value})
            self.output_data[topic][1].update({name: meta})

    def exit(self):
        self.stop()
        sys.exit()

    @Core.receiver('onstop')
    def stop(self, sender, **kwargs):
        """
        Call when agent is stopped close socket.
        :param sender:
        :param kwargs:
        :return:
        """
        if self.socket_server:
            self.socket_server.stop()
            self.socket_server = None

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
        try:
            topic_list = topic.split("/")
            device_topic = "/".join(topic_list[:-1])
            point = topic_list[-1]
            # Retrieve data payload from the output_data.
            data_payload = self.output_data[device_topic]
            value = data_payload[0][point]
        except KeyError as ex:
            # No match for outputs
            value = None
            log.debug('Error on get_point %s', topic)
        return value

    @RPC.export
    def set_point(self, requester_id, topic, value, **kwargs):
        """RPC method

        Sets the value of a specific point on a device.

        :param requester_id: String value deprecated.
        :param topic: The topic of the point to set in the
                      format <device topic>/<point name>
        :param value: Value to set point to.
        :param **kwargs: These get dropped on the floor
        :type topic: str
        :type requester_id: str
        :type value: any basic python type
        :returns: value supplied
        :rtype: any base python type

        """
        log.debug('Modelica agent handle_set')
        log.debug('topic: %s -- value: %s', topic, value)
        try:
            # Retrieve modelica point name from the control_topic_map.
            name = self.control_topic_map[topic]
            # Set the value and enable to true for active control
            # next time a message is sent to Modelica.
            self.control_map[name]['value'] = value
            self.control_map[name]['enable'] = True
        except KeyError as ex:
            # No match for outputs
            log.debug('Topic does not match any know control '
                      'points: %s --- %s', topic, ex)
        try:
            # Remove the point from the controls list
            # once this list is empty we know we have received all the
            # setpoints we are expecting and will send the messge to Modelica.
            self.controls_list.remove(name)
            log.debug('Controls list %s', self.controls_list)
            if not self.controls_list:
                self.send_control_signal(self.current_control)
        except ValueError as ex:
            log.warning('Received duplicate set '
                        'point for topic: %s - name: %s', topic, name)
            if not self.controls_list:
                self.send_control_signal(self.current_control)
        return value

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
        log.debug('Modelica agent revert_point')
        log.debug('topic: %s', topic)
        try:
            # Retrieve modelica point name from the control_topic_map.
            name = self.control_topic_map[topic]
            # Set the value and enable to true for active control
            # next time a message is sent to Modelica.
            self.control_map[name]['enable'] = False
        except KeyError as ex:
            # No match for outputs
            log.debug('Topic does not match any know '
                      'control points: %s --- %s', topic, ex)
            return FAILURE
        try:
            # Remove the point from the controls list
            # once this list is empty we know we have received all the
            # setpoints we are expecting and will send the messge to Modelica.
            self.controls_list.remove(name)
            log.debug('Controls list %s', self.controls_list)
            if not self.controls_list:
                self.send_control_signal(self.current_control)
        except ValueError as ex:
            log.warning('Received duplicate set point '
                        'for topic: %s - name: %s', topic, name)
            if not self.controls_list:
                self.send_control_signal(self.current_control)
        return SUCCESS

    def advance_simulation(self, peer, sender, bus, topic, headers, message):
        """
        Pubsub callback to advance simulation to next timestep.
        Will use current value for any setpoints that have not been received.
        :param peer:
        :param sender: sender is not used
        :param bus:
        :param topic: str
        :param headers: empty, i.e., not used
        :param message: empty, i.e., not used
        :return:
        """
        # if current_control is None then Modelica is not accepting inputs
        while self.current_control is None:
            log.warning('Received advance but Modelica is '
                        'not primed to take inputs!')
            log.warning('Keep checking for Modelica to accept inputs!')
            sleep(1)
        self.controls_list = []
        self.send_control_signal(self.current_control)


def main(argv=sys.argv):
    """Main method called by the eggsecutable."""
    try:
        utils.vip_main(ModelicaAgent)
    except Exception as ex:
        log.exception(ex)


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
