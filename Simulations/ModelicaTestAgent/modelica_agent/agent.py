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


class ModelicaTest(Agent):
    """
    Modelica test.
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

        # Read outputs dictionary and inputs dictionary
        inputs = config.get('inputs', {})
        self.advance_simulation_topic = config.get("advance_simulation_topic")
        self.advance_time = config.get("advance_interval", 30)
        if self.advance_simulation is not None:
            self.core.periodic(self.advance_time, self.advance_simulation, wait=self.advance_time)

    def advance_simulation(self):
        """
        Testing function.
        :return:
        """
        self.vip.pubsub.publish('pubsub',
                                self.advance_simulation_topic,
                                headers={},
                                message={})

    @Core.receiver('onstart')
    def start(self, sender, **kwargs):
        """
        ON agent start call function to instantiate the socket server.
        :param sender: not used
        :param kwargs: not used
        :return:
        """
        pass


def main(argv=sys.argv):
    """Main method called by the eggsecutable."""
    try:
        utils.vip_main(ModelicaTest)
    except Exception as ex:
        log.exception(ex)


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
