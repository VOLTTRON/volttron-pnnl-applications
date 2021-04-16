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


from .helpers import *
from .measurement_type import MeasurementType
from .local_asset import LocalAsset
from .local_asset_model import LocalAssetModel
from .interval_value import IntervalValue


class SolarPvResourceModel(LocalAssetModel, object):
    # SolarPvResourceModel Subclass for renewable solar PV generation The Solar
    # PV resource is treated here as a must-take resource. This is unlike
    # dispatchable resources in this regard. Production may be predicted.
    # The main features of this model are (1) the introduction of property
    # cloudFactor, an IntervalValue, that allows us to reduce the expected
    # solar generation according to cloud cover, and (2) method
    # solar_generation() that creates the envelope, best-case, power production
    # for the resource as a function of time-of-day.

    def __init__(self):
        super(SolarPvResourceModel, self).__init__()
        self.cloudFactor = 1.0

    def schedule_power(self, mkt):
        # Estimate stochastic generation from a solar
        # PV array as a function of time-of-day and a cloud-cover factor.
        # INPUTS:
        # obj - SolarPvResourceModel class object
        # tod - time of day
        # OUTPUTS:
        # p - calcalated maximum power production at this time of day
        # LOCAL:
        # h - hour (presumes 24-hour clock, local time)
        # *************************************************************************

        # Gather active time intervals
        tis = mkt.timeIntervals

        # Index through the active time intervals ti
        for ti in tis:
            # Production will be estimated from the time-of-day at the center of
            # the time interval.
            tod = ti.startTime + ti.duration/2  # a datetime

            # extract a fractional representation of the hour-of-day
            h = tod.hour
            m = tod.minute
            h = h + m / 60  # TOD stated as fractional hours

            # Estimate solar generation as a sinusoidal function of daylight hours.
            if h < 5.5 or h > 17.5:
                # The time is outside the time of solar production. Set power to zero.
                p = 0.0  # [avg.kW]

            else:
                # A sinusoidal function is used to forecast solar generation
                # during the normally sunny part of a day.
                p = 0.5 * (1 + math.cos((h - 12) * 2.0 * math.pi / 12))
                p = self.object.maximumPower * p
                p = self.cloudFactor * p  # [avg.kW]

            # Check whether a scheduled power exists in the indexed time interval.
            iv = find_obj_by_ti(self.scheduledPowers, ti)
            if iv is None:
                # No scheduled power value is found in the indexed time interval.
                # Create and store one.
                iv = IntervalValue(self, ti, mkt, MeasurementType.ScheduledPower, p)
                # Append the scheduled power to the list of scheduled powers.
                self.scheduledPowers.append(iv)

            else:
                # A scheduled power already exists in the indexed time interval.
                # Simply reassign its value.
                iv.value = p  # [avg.kW]

            # Assign engagement schedule in the indexed time interval
            # NOTE: The assignment of engagement schedule, if used, will often be
            # assigned during the scheduling of power, not separately as
            # demonstrated here.

            # Check whether an engagement schedule exists in the indexed time interval
            iv = find_obj_by_ti(self.engagementSchedule, ti)

            # NOTE: this template assigns engagement value as true (i.e., engaged).
            val = True  # Asset is committed or engaged

            if iv is None:
                # No engagement schedule was found in the indexed time interval.
                # Create an interval value and assign its value.
                iv = IntervalValue(self, ti, mkt, MeasurementType.EngagementSchedule, val)  # an IntervalValue

                # Append the interval value to the list of active interval values
                self.engagementSchedule.append(iv)

            else:
                # An engagement schedule was found in the indexed time interval.
                # Simpy reassign its value.
                iv.value = val  # [$]

        # Remove any extra scheduled powers
        self.scheduledPowers = [x for x in self.scheduledPowers if x.timeInterval in tis]

        # Remove any extra engagement schedule values
        self.engagementSchedule = [x for x in self.engagementSchedule if x.timeInterval in tis]


if __name__ == '__main__':
    spvm = SolarPvResourceModel()
