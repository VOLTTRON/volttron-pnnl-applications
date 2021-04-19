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


from .auction import Auction
from .market_state import MarketState
from datetime import timedelta
from .real_time_auction import RealTimeAuction
from .data_manager import *

class DayAheadAuction(Auction):

    def __init__(self):
        super(DayAheadAuction, self).__init__()

    def spawn_markets(self, this_transactive_node, new_market_clearing_time):

        # 200910DJH: This is where you may change between 15-minute and 60-minute real-time refinement intervals.
        real_time_market_duration = timedelta(minutes=self.real_time_duration)

        # First, go ahead and use the base method and current market to create the next member of this market series,
        # as was intended. This should instantiate the new market,  create its time intervals, and initialize marginal
        # prices for the new market.
        Auction.spawn_markets(self, this_transactive_node, new_market_clearing_time)

        # Next, the new day-ahead market instantiates all the real-time markets that will correct the new day-ahead
        # intervals. There are several ways to retrieve the market that was just created, but this approach should be
        # pretty foolproof.
        market = [x for x in this_transactive_node.markets if x.marketClearingTime == self.nextMarketClearingTime and
                      x.marketSeriesName == self.marketSeriesName][0]

        # Something is seriously wrong if the recently instantiated market cannot be found. Raise an error and stop.
        # if market is None or len(market) == 0:
        if market is None:
            raise ('No predecessor of ' + self.name + ' could be found.')

        # Gather all the day-ahead market period start times and order them.
        market_interval_start_times = [x.startTime for x in market.timeIntervals]
        market_interval_start_times.sort()

        # 210401DJH: This initialization of new_market_list had been misplaced, thus causing only the final hour's Real-
        #            Time markets to be captured as CSV records. It should be initialized prior to looping through the
        #            Day-Ahead market hours, as placed here.
        new_market_list = []

        for i in range(len(market_interval_start_times)):

            interval_start = market_interval_start_times[i]
            interval_end = interval_start + market.intervalDuration

            # 210401DJH: This initialization of new_market_list is misplaced, thus causing only the final hour's Real-
            #            Time markets to be captured as CSV records.
            # new_market_list = []
            while interval_start < interval_end:

                # Instantiate a new real-time market.
                new_market = RealTimeAuction()

                new_market.marketToBeRefined = market
                new_market.intervalToBeRefined = [x for x in market.timeIntervals
                                                  if x.startTime == market_interval_start_times[i]]

                # Set the lead times. This is done explicitly.
                # 200910DJH: Please use real_time_market_duration to change between real-time market interval durations.
                #  new_market.marketClearingInterval = timedelta(minutes=15)
                new_market.marketClearingInterval = real_time_market_duration

                new_market.marketSeriesName = "Real-Time Auction"
                new_market.deliveryLeadTime = timedelta(minutes=5)
                new_market.marketLeadTime = timedelta(minutes=5)
                new_market.negotiationLeadTime = timedelta(minutes=5)

                # Find the prior market in this series. It should be the one that shares the same market series name and
                # is, until now, the newest market in the series.
                prior_market = [x for x in this_transactive_node.markets
                                if x.marketSeriesName == new_market.marketSeriesName
                                and x.isNewestMarket is True]

                if prior_market is None or len(prior_market) == 0:

                    # This is most likely a startup issue when the prior market in the series cannot be found.
                    Warning('No prior markets were found in market series: ' + new_market.marketSeriesName)
                    new_market.priceModel = self.priceModel
                    new_market.defaultPrice = self.defaultPrice
                    new_market.futureHorizon = new_market.marketClearingInterval

                else:

                    # The prior market was found. These attributes may be adopted from the prior market in the series.
                    prior_market = prior_market[0]
                    prior_market.isNewestMarket = False
                    new_market.priceModel = prior_market.priceModel
                    new_market.defaultPrice = prior_market.defaultPrice
                    new_market.futureHorizon = prior_market.futureHorizon
                    new_market.priorMarketInSeries = prior_market

                new_market.commitment = False
                new_market.initialMarketState = MarketState.Inactive

                # 200910DJH: Please use the real-time_market_duration constant to modify real-time market intervals.
                # new_market.intervalDuration = timedelta(minutes=15)
                new_market.intervalDuration = real_time_market_duration

                new_market.intervalsToClear = 1
                new_market.marketOrder = 2
                new_market.method = 2
                new_market.marketState = new_market.initialMarketState
                new_market.marketClearingTime = interval_start - new_market.deliveryLeadTime
                new_market.nextMarketClearingTime = new_market.marketClearingTime + new_market.marketClearingInterval

                # The market instance is named by concatenating the market name and its market clearing time.
                dt = str(new_market.marketClearingTime)
                new_market.name = new_market.marketSeriesName.replace(' ', '_') + '_' + dt[:19]

                # Pass the flag for the newest market in the market series. This important flag will be needed
                # to find this new market when the succeeding one is being instantiated and configured.
                new_market.isNewestMarket = True  # This new market now assumes the flag as newest market

                # Initialize the new market object's time intervals.
                new_market.check_intervals()

                # Initialize the marginal prices in the new market object's time intervals.
                new_market.check_marginal_prices(this_transactive_node)

                # Append the new market object to the list of active market objects that is maintained by the agent.
                this_transactive_node.markets.append(new_market)

                # Calculate the next interval's start time.
                interval_start = interval_start + new_market.intervalDuration

                # 210127DJH: Add the newly created market to a list.
                new_market_list.append(new_market)

        # 210127DJH: Capture the new markets to a formatted csv datafile.
        append_table(obj=new_market_list)
