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

# TODO: Revisit the simulation features of class Timer that may have been lost by directly using datetime methods.

from datetime import datetime
#from volttron.platform.agent import utils


class Timer(object):
    created_time = None
    sim_one_hr_in_sec = 1200
    sim_start_time = None
    simulation = False

    @classmethod
    def get_cur_time(cls):
        """
        Calculate current time based on the amount of time has passed since this object is created
        :return:
        """
        #cur_time = utils.get_aware_utc_now()
        cur_time = datetime.now()
        if cls.simulation:
            ratio = 3600 / cls.sim_one_hr_in_sec
            time_diff = cur_time - cls.created_time
            simulation_time_diff = time_diff * ratio
            cur_time = cls.sim_start_time + simulation_time_diff

        return cur_time


if __name__ == '__main__':
    from dateutil import parser

    Timer.simulation = True
    Timer.created_time = parser.parse("2018-07-18 16:01:00.000")

    Timer.sim_start_time = parser.parse("2018-06-22 00:00:00.000")
    print(Timer.get_cur_time())

    Timer.sim_start_time = parser.parse("2018-07-22 00:00:00.000")
    print(Timer.get_cur_time())

    Timer.simulation = False
    print(Timer.get_cur_time())
