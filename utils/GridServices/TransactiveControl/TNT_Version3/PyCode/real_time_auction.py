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

import logging

from .auction import Auction
from .timer import Timer
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.agent.utils import format_timestamp

utils.setup_logging()
_log = logging.getLogger(__name__)


class RealTimeAuction(Auction):

    def __init__(self):
        super(RealTimeAuction, self).__init__()

    def spawn_markets(self, this_transactive_node=None, new_market_clearing_time=None):
        # In this case, the real-time auctions are spawned by the day-ahead markets. Therefore, the real-time markets
        # should not instantiate ANY market objects. The base class method is replaced.
        pass
    
    def transition_from_delivery_lead_to_delivery(self, my_transactive_node):
        """
        For activities that should accompany a market object's transition from market state "DeliveryLead" to
        "Delivery." This method may be overwritten by child classes of Market to create alternative market behaviors
        during this transition.
        :param my_transactive_node: transactive node object--this agent
        :return: None
        """
        k = 4*14
        # A good practice upon entering the delivery period is to update the market's price model using the final
        # marginal prices.
        final_prices = self.marginalPrices
        for x in range(len(final_prices)):
            self.model_prices(final_prices[x].timeInterval.startTime, final_prices[x].value, k=k)

        self.deliverylead_schedule_power = False

        _log.debug(f"{self.name}: transition_from_delivery_lead_to_delivery")

        headers = {headers_mod.DATE: format_timestamp(Timer.get_cur_time())}
        msg = dict()
        msg['tnt_market_name'] = self.name
        my_transactive_node.vip.pubsub.publish(peer='pubsub',
                                               topic=my_transactive_node.market_balanced_price_topic,
                                               headers=headers,
                                               message=msg)
        self.publish_records(my_transactive_node)
        return None
