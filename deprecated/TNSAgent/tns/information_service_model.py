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



from datetime import timedelta

from .measurement_type import MeasurementType
from .measurement_unit import MeasurementUnit
from .interval_value import IntervalValue


class InformationServiceModel:
    # InformationServiceModel Base Class
    # An InformationServiceModel manages an InformationService and predicts or
    # interpolates the information it provides.

    def __init__(self):
        # InformationService
        self.address = ''  # perhaps a web address storage
        self.description = ''
        self.informationType = MeasurementType.Unknown
        self.informationUnits = MeasurementUnit.Unknown
        self.license = ''
        self.nextQueryTime = None  # datetime.empty
        self.serviceExpirationDate = None  # datetime.empty
        self.updatePeriod = timedelta(hours=1)  # [h]

        # InformationServiceModel properties
        self.file = ''  # filename having entries for time intervals
        self.name = ''
        self.nextScheduledUpdate = None  # datetime.empty
        self.predictedValues = []  # IntervalValue.empty
        self.updateInterval = timedelta(hours=1)  # [h]


    # This template is available to conduct the forecasting of useful information.
    @classmethod
    def update_information(ism, mkt):
        #   Gather active time intervals ti
        ti = mkt.timeIntervals

        #   index through active time intervals ti
        for i in range(len(ti)):  # for i = 1:length(ti)
            #       Get the start time for the indexed time interval
            st = ti(i).startTime

            #       Extract the starting time hour
            hr = st.hour

            #       Look up the value in a table. NOTE: tables may be used during
            #       development until active information services are developed.
            # Is the purpose of this one to read MODERATE weather temperature? YES
            T = readtable(ism.file)
            value = T(hr + 1, 1)

            #       Check whether the information exists in the indexed time interval
            # Question: what is ism? InformationServiceModel doesn't have 'values' as well as 'iv' properties.
            #   Suggestion: use long name as much as possible
            #   Need an example on what this one does. Really need a unit test here?
            #iv = findobj(ism.values, 'timeInterval', ti(i))
            iv = [x for x in ism.values if x.timeInterval.startTime == ti[i].startTime]  #
            iv = iv[0] if len(iv)>0 else None

            if iv is None:  # isempty(iv):
                # The value does not exist in the indexed time interval. Create it and store it.
                #iv = IntervalValue(ism, ti(i), mkt, 'Temperature', value)
                iv = IntervalValue(ism, ti[i], mkt, MeasurementType.Temperature, value)
                ism.values = [ism.values, iv]

            else:
                # The value exists in the indexed time interval. Simply reassign it
                iv.value = value

    # Not sure when to use this yet
    #events
    #    UpdatedInformationReceived


if __name__ == '__main__':
    pass
