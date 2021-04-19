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

from datetime import datetime

from .time_interval import TimeInterval
from .helpers import format_ts


class TransactiveRecord:
    def __init__(self, ti, rn, mp, p, pu=0.0, cost=0.0, rp=0.0, rpu=0.0, v=0.0, vu=0.0):
        # NOTE: As of Feb 2018, ti is forced to be text, the time interval name,
        # not a TimeInterval object.
        # ti - TimeInterval object (that must be converted to its name)
        # rn - record number, a nonzero integer
        # mp - marginal price [$/kWh]
        # p  - power [avg.kW]

        # These are the four normal arguments of the constructor.
        # NOTE: Use the time interval ti text name, not a TimeInterval object itself.
        if isinstance(ti, TimeInterval):
            # A TimeInterval object argument must be represented by its text name.
            self.timeInterval = ti.name

        else:
            # Argument ti is most likely received as a text string name. Further
            # validation might be used to make sure that ti is a valid name of an
            # active time interval.
            self.timeInterval = ti

        self.record = rn  # a record number (0 refers to the balance point)
        self.marginalPrice = mp  # marginal price [$/kWh]
        self.power = p  # power [avg.kW]

        # Source and target are obvious from Neighbor and filenames. Omit
        # self.powerUncertainty = pu  # relative [dimensionless]
        self.cost = cost  # ?
        # self.reactivePower = rp  # [avg.kVAR]
        # self.reactivePowerUncertainty = rpu  # relative [dimensionless]
        # self.voltage = v  # [p.u.]
        # self.voltageUncertainty = vu  # relative [dimensionless]

        # Finally, create the timestamp that captures when the record is created.
        self.timeStamp = datetime.utcnow()
