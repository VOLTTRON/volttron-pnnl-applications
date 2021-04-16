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


# BPA_RATE: BPA 2018-19 energy and demand rate tables
# BPA establishes load-following energy and demand rates for two-year
# periods. Use this class to simply refer to the appropriate table and its
# month number(row) and hour type (row). Row 1 is HLH, row 2 is LLH.
#
# Examples: bpa_rate.energy(2,1) returns the HLH rate for February.
#           bpa_rate.demand(3,2) returns the LLH demand rate for March.

## Constant bpa_rate properties

bpa_energy_rate = [
    #HLH,     LLH       # [$/kWh]
    [0.04196, 0.03660],  # Jan
    [0.04120, 0.03660],  # Feb
    [0.03641, 0.03346],  # Mar
    [0.03233, 0.03020],  # Apr
    [0.02929, 0.02391],  # May
    [0.03037, 0.02197],  # Jun
    [0.03732, 0.03171],  # Jul
    [0.04077, 0.03527],  # Aug
    [0.04060, 0.03485],  # Sep
    [0.03940, 0.03515],  # Oct
    [0.03993, 0.03740],  # Nov
    [0.04294, 0.03740]  # dec
]

bpa_demand_rate = [
    # HLH,     LLH       # [$/kWh]
    [11.45, 0.00],  # Jan
    [11.15, 0.00],  # Feb
    [9.28, 0.00],  # Mar
    [7.68, 0.00],  # Apr
    [6.49, 0.00],  # May
    [6.92, 0.00],  # Jun
    [9.63, 0.00],  # Jul
    [10.98, 0.00],  # Aug
    [10.91, 0.00],  # Sep
    [10.45, 0.00],  # Oct
    [10.65, 0.00],  # Nov
    [11.83, 0.00]  # dec
]
