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

from datetime import datetime, timedelta

from .market_state import MarketState
from .helpers import format_ts
from .timer import Timer

# import logging
"""
utils.setup_logging()
_log = logging.getLogger(__name__)
"""


class TimeInterval(object):
    """
    The TimeInterval is the Market time interval. It progresses through
    a series of MarketStates (see MarketState enumeration).
    """

    def __init__(self, activation_time, duration, market, market_clearing_time, start_time):
        self.active = False  # Boolean
        self.marketState = MarketState.Inactive  # members are enumeration
        self.timeStamp = None  # datetime.empty  # when interval is created/modified

        # ACTIVATION TIME - datetime that the TimeInterval becomes Active and
        # enters the Exploring market state
        self.activationTime = activation_time  # datetime(at)

        # CONVERGED - convergence flag for possible future use
        self.converged = False

        # DURATION - duration of interval[hr]
        # Ensure that content is a duration [hr]
        if isinstance(duration, timedelta):
            self.duration = duration

        # MARKET - Market object that uses this TimeInterval
        self.market = market

        # MARKET CLEARING TIME - time that negotiations stop. Time that
        # commitments, if used, are in force.
        self.marketClearingTime = market_clearing_time  # datetime(mct)

        # START TIME - time that interval period begins
        self.startTime = start_time  # datetime(st)

        # NAME
        # 201009DJH: In Version 3, where there can be multiple simultaneous time intervals, let's try appending the
        #            market name to make sure the time interval is unique to its market.
        # self.name = helpers.format_ts(self.startTime)
        self.name = str(self.market.marketSeriesName) + ":" + format_ts(self.startTime)

        # RECONCILED - reconciliation flag for possible future use
        self.reconciled = False

        # MARKET STATE - an enumeration of market states, concerning the
        #                status of negotiations on this time interval.
        # ACTIVE - logical true during negotiations, delivery, and
        #          reconcilliation of the time interval
        # TIME STAMP - the time the the time interval is created or modified
        # NOTE 1911DJH: The market state of an interval is no longer relevant. A Market owns its market state, and the
        # market state is relevant to all of its included market time intervals.
        # self.assign_state(market)

    def assign_state(self, market):
        # assign_state - assign state of the TimeInterval in its Market.
        # Enumeration MarketState has all the allowed market state names.
        # obj - a TimeInterval oject. Invoke as "self.assign_state(market)".
        # market - Market object (see class Market).

        dt = Timer.get_cur_time()

        # State "Expired": The TimeInterval period is over and the interval has
        # been reconciled in its Market.
        if (dt >= self.startTime + self.duration) and self.reconciled:
            self.marketState = MarketState.Expired
            self.active = False
            self.timeStamp = dt

        # State "Publish": The TimeInterval period has expired, but it has not
        # yet been reconciled in its Market.
        elif dt >= self.startTime + self.duration:
            self.marketState = MarketState.Publish
            self.active = True
            self.timeStamp = dt

        # State "Delivery": Current datetime is within the interval period.
        elif dt >= self.startTime:
            self.marketState = MarketState.Delivery
            self.active = True
            self.timeStamp = dt

        # State "Transaction": Current datetime exceeds the market clearing time.
        elif dt >= self.marketClearingTime:
            self.marketState = MarketState.Transaction
            self.active = True
            self.timeStamp = dt

        # State "Tender": TimeInterval is both active and converged.
        elif dt >= self.activationTime and self.converged:
            self.marketState = MarketState.Tender
            self.active = True
            self.timeStamp = dt

        # State "Exploring": TimeInterval is active, but it has not converged.
        elif dt >= self.activationTime:
            self.marketState = MarketState.Exploring
            self.active = True
            self.timeStamp = dt

        # State "Inactive": The TimeInterval has not yet become active.
        elif dt < self.activationTime:
            self.marketState = MarketState.Inactive
            self.active = False
            self.timeStamp = dt

        else:
            """
            logging.basicConfig(level=logging.DEBUG,
                                format='%(asctime)s %(module)s %(name)s.%(funcName)s +%(lineno)s: %(levelname)-8s [%(process)d] %(message)s',
                                )
            """
#            _log.log(logging.ERROR, 'Invalid TimeInterval market state: TimeInterval ' + self.name)

    def getDict(self):
        time_interval_dict = {
            "startTime": self.startTime,
            "name": self.name,
            "duration": self.duration
        }
        return time_interval_dict


if __name__ == '__main__':
    # Dummy values for testing
    activation_time = datetime.now()
    duration = timedelta(hours=1)
    market_clearing_time = datetime.now()
    start_time = datetime.now()

    ti = TimeInterval(activation_time, duration, None, market_clearing_time, start_time)
