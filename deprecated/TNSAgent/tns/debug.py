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


def test_aredifferent1(r, s, threshold):
    import math

    s_power=s[0][2]
    s_mp=s[0][3]

    r_power=r[0][2]
    r_mp=r[0][3]

    # Calculate the difference dmp in scheduled marginal prices.
    dmp = abs(s_mp - r_mp)  # [$/kWh]

    # Calculate the average mp_avg of the two scheduled marginal prices.
    mp_avg = 0.5 * abs(s_mp + r_mp)  # [$/kWh]

    # Calculate the difference dq betweent the scheduled powers.
    dq = abs(-s_power - r_power)  # [avg. kW]

    # Calculate the average q_avg of the two scheduled average powers.
    q_avg = 0.5 * abs(r_power + -s_power)  # [avg. kW]


    if q_avg != 0:
        if len(s) == 1 or len(r) == 1:
            d = dq / q_avg  # dimensionless
        else:
            d = math.sqrt((dq / q_avg) ** 2 + (dmp / mp_avg) ** 2)  # dimensionless
    else:
        d = 0

    if d > threshold:
        # The distance, or relative error, between the two scheduled points
        # exceeds the threshold criterion. Return true to indicate that the
        # two messages are significantly different.
        is_diff = True

    else:
        # The distance, or relative error, between the two scheduled points
        # is less than the threshold criterion. Return false, meaning that
        # the two messages are not significantly different.
        is_diff = False

    print(is_diff)


if __name__ == '__main__':
    # Return: True   d = math.sqrt((dq / q_avg) ** 2 + (dmp / mp_avg) ** 2) = 0.04x
    threshold = 0.02
    r = [('20180622T020000', 0, 37.2684974345231, 0.022220484745369),
         ('20180622T020000', 1, 0.0, 0.022219983435294),
         ('20180622T020000', 2, 110.0, 0.022221463079283)]
    s = [('20180622T020000', 0, -38.14998337529896, 0.021457224582343865),
         ('20180622T020000', 1, -40.11329301604832, 0.01975728208437844),
         ('20180622T020000', 2, -20.969231491568785, 0.03633327350909643)]
    test_aredifferent1(r, s, threshold)
