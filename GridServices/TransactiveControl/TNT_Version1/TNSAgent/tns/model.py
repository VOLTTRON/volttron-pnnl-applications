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


from .vertex import Vertex
from .time_interval import TimeInterval
from .local_asset import LocalAsset
from .interval_value import IntervalValue


class Model:
    def __init__(self):
        """
        Top-level class for all transactive model classes
        """

        # Name of the model
        self.name = 'Model'

        # Location where this model is created (eg. BUILDING1)
        self.location = 'ModelLocation'

        # An array of vertices that represent the production of a resource
        # (or consumption of load) as a function of marginal price.
        self.activeVertices = []  # IntervalValue

        # Three coefficients [a(1),a(2),a(3)] that may be used to calculate
        # production cost of resources (or gross consumer surplus (i.e., utility) for loads?).
        #   cost = a(3)*p^2 + a(2)*p + a(1) [$/h]
        self.costParameters = [0.0, 0.0, 0.0]  # {mustBeReal}

        # Array of vertices that may be used to initialize price behaviors.
        self.defaultVertices = [Vertex(float("inf"), 0.0, 1)]

        # Array of dual costs for each active time interval. For a neighbor,
        # the dual cost is equal to production surplus (aka "profit"), plus
        # other Lagrangian and constraint terms during the importation of
        # electricity. During the exportation of electricity, dual costs
        # include the (net) consumer surplus, plus other Lagrangian terms [$]
        self.dualCosts = []  # IntervalValue

        # Array of meter points called upon by this model. [See class MeterPoint.]
        self.meterPoints = []  # MeterPoint

        # Cross reference from this model to the corresponding neighbor object.
        self.object = None

        # Array of production costs for active time intervals. For a
        # neighbor, production costs apply only during the importation of
        # electricity. [$]
        self.productionCosts = []  # IntervalValue[]

        # Array of margins between maximum and scheduled powers in active
        # time intervals. An estimate of spinning reserve is tracked. The
        # long-term goal is to solve for a target reserve margin, but doing
        # so requires having multiple resource that may be engaged or
        # disengaged, spinning or non-spinning. [avg.kW]
        self.reserveMargins = []  # IntervalValue[]

        # Array of scheduled real power for this resource in each of the
        # active time intervals. Values should be positive for imported
        # power negative for exported. [avg. kW]
        self.scheduledPowers = []  # IntervalValue

        # Sum of dual costs for the entire set of future time horizon
        # intervals. [$]
        self.totalDualCost = 0.0  # real

        # Sum of production costs for the entire set of future time horizon
        # intervals. This should not include gross consumer surplus during
        # exportation of electricity to the neighbhor. [$]
        self.totalProductionCost = 0.0  # {mustBeReal, mustBeNonnegative}

        # Volttron
        self.mtn = None
        self.power_topic = ''
        self.system_loss_topic = ''
        self.dc_threshold_topic = ''

    def inject(self, mtn, power_topic='', system_loss_topic='', dc_threshold_topic=''):
        self.mtn = mtn
        self.power_topic = power_topic
        self.system_loss_topic = system_loss_topic
        self.dc_threshold_topic = dc_threshold_topic

    def schedule(self, mkt):
        """
        Have object schedule its power in active time intervals
        :param mkt:
        :return:
        """
        pass

    def update_costs(self, mkt):
        """
        Have model object update and store its costs
        :param mkt:
        :return:
        """

        # Initialize sums of production and dual costs
        self.totalProductionCost = 0.0
        self.totalDualCost = 0.0

        # Have object update and store its production and dual costs in
        # each active time interval
        self.update_production_costs(mkt)
        self.update_dual_costs(mkt)

        # Sum total production and dual costs through all time intervals
        self.totalProductionCost = sum([x.value for x in self.productionCosts])
        self.totalDualCost = sum([x.value for x in self.dualCosts])

    # These abstract methods must be redefined (made concrete) by NeighborModel
    # and LocalAssetModel subclasses. (This requirement is met by simply doing
    # so in the LocalAssetModel and NeighborModel base classes.)
    def calculate_reserve_margin(self, mkt):
        pass

    def schedule_power(self, mkt):
        pass

    def update_dual_costs(self, mkt):
        pass

    def update_production_costs(self, mkt):
        pass

    def update_vertices(self, mkt):
        pass

    def schedule_engagement(self, mkt):
        pass


if __name__ == '__main__':
    model = Model()
