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
from volttron.platform.agent import utils

from .helpers import *
from .measurement_type import MeasurementType
from .interval_value import IntervalValue
from .neighbor_model import Neighbor
from .const import *
from .vertex import Vertex
from .timer import Timer
from .market_state import MarketState
from .data_manager import append_table

utils.setup_logging()
_log = logging.getLogger(__name__)


class BulkSupplier_dc(Neighbor):
    # BulkSupplier Neighbor subclass - Represents non-transactive neighbor, including demand charges
    #
    # Created to represent large, non-transactive electricity supplier BPA in its relationship to a municipality.
    # - Introduces new properties to keep track of peak demand.
    # - Calls on a new function to determine hour type (HLH or LLH).
    # - Mines tables to determine monthly electricity and demand rates in HLH and LLH hour types.

    def __init__(self):
        super(BulkSupplier_dc, self).__init__()
        self.transactive = False

    def update_vertices(self, market):
        # Creates active vertices for a non-transactive neighbor, including demand charges.
        #
        # INPUTS:
        # mkt - Market object
        #
        # OUTPUTS:
        # - Updates self.activeVertices for active time intervals.
        #
        # 200804DJH: Method was revised to be more concise and consistent with Version-3 practices:
        #            - Active vertices are first created from the perspective of the bulk supplier.
        #            - New method 'include_marginal_losses()' is then used to modify the vertices to include the impacts
        #              of marginal losses. This reduces the available supply power and increases the effective marginal
        #              price to account for energy losses.
        #            - New method 'include_demand_charges()' is then used to include demand charges.
        #              - Correcting tracking of scheduled powers by demand-charge threshold, which had been turned off.

        # Gather active market time intervals [TimeInterval]
        time_intervals = market.timeIntervals

        # Get the maximum and minimum power for this neighbor [kW]
        maximum_power = self.maximumPower
        minimum_power = self.minimumPower

        # The maximum power property is meaningful for both imported (p>0) and exported (p<0) electricity, but this
        # formulation is intended for importation (power>0) from an electricity supplier. Warn the user and return if
        # the maximum power is negative.
        if maximum_power < 0 or minimum_power < 0:
            _log.warning('You should not use neighbor object ' + self.name
                    + ' with class BulkSupplier_DC that represents a bulk supplier.')
            return

        # Cost coefficient a0. This is unavailable from a supply curve, so it must be determined directly from the
        # first, constant cost parameter. It does NOT affect marginal pricing [$/h].
        a0 = self.costParameters[0]

        # Initialize thresholds that will be used to apply demand charges.
        demand_threshold = self.demandThreshold
        active_threshold = demand_threshold

        # 210331DJH: This is an error for markets that have multiple market time intervals. If initialized here, each
        #            successive time interval adds to the list of vertices, each having been potentially modified by the
        #            prior calculations. This initialization belongs *INSIDE* teh time interval loop.
        # Initialize the list of vertices that are to become the active vertices.
        # vertices = []

        # 210321DJH:
        new_active_vertices = []

        # Index through active time intervals.
        for i in range(len(time_intervals)):

            # Pick out the indexed time interval.
            time_interval = time_intervals[i]

            # 210331DJH: This initialization fixes a logic error for markets that have multiple market time intervals.
            #            The initialization belongs *INSIDE* teh time interval loop.
            #            BTW, the mistake was not found during unit testing because unit testing did not challenge the
            #            method with multiple time periods.
            # Initialize the list of vertices that are to become the active vertices.
            vertices = []

            # Find the month number for the indexed time interval start time. The month is needed for rate lookup
            # tables.
            month_number = time_interval.startTime.month

            if is_heavyloadhour(time_interval.startTime):
                price = bpa_energy_rate[month_number - 1][0]  # HLH energy rate [$/kWh]
            else:
                price = bpa_energy_rate[month_number - 1][1]  # bpa_energy_rate(month_number, 2)

            vertices.append(Vertex(marginal_price=price,
                                   power=minimum_power,
                                   prod_cost=a0 + price * minimum_power
                                   )
                            )

            vertices.append(Vertex(marginal_price=price,
                                   power=maximum_power,
                                   prod_cost=a0 + price * maximum_power
                                   )
                            )

            # At this point the two vertices capture the remote supplier's perspective.

            # Modify the vertices to include the impacts of marginal losses.
            if self.lossFactor != 0:
                vertices = self.include_marginal_losses(vertices=vertices)

            # Modify the vertices to include the impacts of demand charges.
            # Make sure that the demand_rate is set to the current demand rate.
            self.demandRate = bpa_demand_rate[month_number - 1][0]

            '''_log.debug("UV: active_threshold: {}, demandRate: {}".format(active_threshold, self.demandRate))
            _log.debug("UV: time interval: {}".format(time_interval.startTime))
            for x in vertices:
                _log.debug("UV: ({}, {}, {})".format(x.record, x.marginalPrice, x.power))
            '''
            # Demand Charges only apply to HLH hours.
            if is_heavyloadhour(time_interval.startTime) and self.demandRate != 0:
                scheduled_power = [x.power for x in self.scheduledPowers if x.timeInterval == time_interval]
                if scheduled_power is not None and len(scheduled_power) != 0:
                    active_threshold = max(active_threshold, scheduled_power[0])
                vertices = self.include_demand_charges(vertices=vertices, threshold=active_threshold)

            # Find and delete active vertices in the indexed time interval. These vertices shall be re-created.
            # 200925DJH: This already had an error in attempting equivalence between a time interval and interval value.
            #            Otherwise, it should be fine for Version 3 because a time interval object is unique to its
            #            market.
            # self.activeVertices = [x for x in self.activeVertices if x != time_intervals[i]]
            self.activeVertices = [x for x in self.activeVertices if x.timeInterval != time_interval]

            # Save the corrected vertices as active vertices interval values.
            for v in range(len(vertices)):

                # Pick out the indexed vertex.
                vertex = vertices[v]

                # Append the vertex to the neighbor's active vertices as interval values.
                new_active_vertices.append(IntervalValue(calling_object=self,
                                                         time_interval=time_interval,
                                                         market=market,
                                                         measurement_type=MeasurementType.ActiveVertex,
                                                         value=vertex
                                                         )
                                           )

        # 210331DJH: This modification using "new_active_vertices" allows the new active vertices to be captured easily
        #            as CSV records.
        self.activeVertices.extend(new_active_vertices)
        append_table(obj=new_active_vertices)

        # 200929DJH: Trim any active vertices that lie in expired markets.
        self.activeVertices = [x for x in self.activeVertices if x.market.marketState != MarketState.Expired]

    def old_update_vertices(self, mkt):
        # 200804DJH: Replaced. Newer version should be consistent with Version 3 treatment of demand charges and losses.
        #            Also observe that demand-charge threshold logic was corrupted to never track scheduled powers.
        # Creates active vertices for a non-transactive neighbor, including demand
        # charges.
        #
        # INPUTS:
        # mkt - Market object
        #
        # OUTPUTS:
        # - Updates self.activeVertices for active time intervals.

        # Gather active time intervals
        time_intervals = mkt.timeIntervals  # TimeInterval objects

        # Get the maximum power maxp for this neighbor.
        maximum_power = self.maximumPower  # [avg.kW]

        # The maximum power property is meaningful for both imported (p>0) and
        # exported (p<0) electricity, but this formulation is intended for
        # importation (power>0) from an electricity supplier. Warn the user and
        # return if the maximum power is negative.
        if maximum_power < 0:
            _log.warning('Maximum power must be positive in BulkSupplier_dc.m')
            _log.warning('Returning without creating active vertices for ' + self.name)
            return

        # Get the minimum power for this neighbor.
        minimum_power = self.minimumPower  # [avg.kW]

        # Only importation is supported from this non-transactive neighbor.
        if minimum_power < 0:
            _log.warning('Minimum power must be positive in "BulkSupplier_dc.m')
            _log.warning('Returning without creating active vertices for ' + self.name)
            return

        # Cost coefficient a0. This is unavailable from a supply curve, so it must be determined directly from the
        # first, constant cost parameter. It does NOT affect marginal pricing.
        a0 = self.costParameters[0]  # [$/h]

        # Full-power loss at is defined by the loss factor property and the maximum power.
        full_power_loss = maximum_power * self.lossFactor  # [avg.kW]

        # Minimum-power loss at Vertex 1 is a fraction of the full-power loss. (Power losses are modeled proportional to
        # the square of power transfer.)
        minimum_power_loss = (minimum_power / maximum_power) ** 2 * full_power_loss  # [avg.kW]

        # Index through active time intervals.
        for i in range(len(time_intervals)):

            # Find and delete active vertices in the indexed time interval. These vertices shall be recreated.
            self.activeVertices = [x for x in self.activeVertices if x != time_intervals[i]]

            # Find the month number for the indexed time interval start time. The month is needed for rate lookup
            # tables.
            month_number = time_intervals[i].startTime.month

            if is_heavyloadhour(time_intervals[i].startTime):

                # The indexed time interval is an HLH hour. The electricity rate is a little higher during HLH hours,
                # and demand-charges may apply. Look up the BPA energy rate for month_number. The second parameter is
                # HLH = 1 (i.e., column 1 of the table).
                energy_rate = bpa_energy_rate[month_number - 1][0]  # HLH energy rate [$/kWh]

                # Four active vertices are initialized:
                # #1 at minimum power
                # #2 at the demand-charge power threshold
                # #3 at the new demand rate and power threshold
                # #4 at maximum power and demand rate
                vertices = [Vertex(0, 0, 0), Vertex(0, 0, 0), Vertex(0, 0, 0), Vertex(0, 0, 0)]

                # Evaluate the first of the four vertices
                # Segment 1: First-order parameter a1.
                # This could be stated directly from cost parameters, but this model allows for dynamic rates, accounts
                # for losses, and models demand-charges, which would require defining multiple cost-parameter models.
                # The first-order parameter is the electricity rate. In this model, the rate is meaningful at a neighbor
                # node location at zero power transfer.
                a1 = energy_rate  # [$/kWh]

                # Vertex 1: Full available power transfer at Vertex 1 is thus the physical transfer limit, minus losses.
                vertices[0].power = (minimum_power - minimum_power_loss)

                # Vertex 1: Marginal price of Vertex 1 is augmented by the value of energy from the neighbor that is
                # lost. (This model assigns the cost of losses to the recipient (importer) of electricity.)
                vertices[0].marginalPrice = a1 * (1 + self.lossFactor * minimum_power / maximum_power)  # [$/kWh]

                # Evaluate the second of four vertices
                # Vertex 2: Available power at Vertex 2 is determined by the current peak demand charge threshold pdt
                # and possibly scheduled powers prior to the indexed time interval. The demand threshold in the indexed
                # time interval is at least equal to the parameter. NOTE this process will work only if the demand
                # threshold is is updated based on actual, accurate measurements.
                peak_demand_threshold = self.demandThreshold  # [kW]

                # Also consider, however, scheduled powers prior to the indexed interval that might have already set a
                # new demand threshold. For simplicity, presume that new demand thresholds would occur only during HLH
                # hour types. More complex code will be needed if only HLH hours must be considered. NOTE this process
                # will work only if the load forcasts are meaningful and accurate.

                # Gather scheduled powers.
                scheduled_powers = self.scheduledPowers
                _log.debug("bulk_supplier_dc: update_vertices: peak_demand_threshold: {}, scheduled_powers: {}".format(
                    peak_demand_threshold, [x.value for x in self.scheduledPowers]))
                if len(scheduled_powers) == 0:

                    # Powers have been scheduled, order the scheduled powers by their start time
                    ordered_scheduled_powers = sorted(self.scheduledPowers, key=lambda x: x.timeInterval.startTime)
                    ordered_scheduled_powers = ordered_scheduled_powers[:i + 1]

                    # The peak demand determinant is the greater of the monthly peak threshold or the prior scheduled
                    # powers.
                    ordered_scheduled_powers = [x.value for x in ordered_scheduled_powers]
                    ordered_scheduled_powers.append(peak_demand_threshold)
                    peak_demand_threshold = max(ordered_scheduled_powers)  # kW

                # Vertex 2: The power at which demand charges will begin accruing and therefore marks the start of
                # Vertex 2. It is not affected by losses because it is based on local metering.
                vertices[1].power = peak_demand_threshold  # [avg.kW]

                # Vertex 2: Marginal price of Vertex 2 is augmented by the value of energy from the neighbor that is
                # lost.
                vertices[1].marginalPrice = a1 * (
                            1 + self.lossFactor * vertices[1].power / maximum_power)  # [$/kWh]

                # Evaluate the third of four vertices Look up the demand rate for the month_number. The second
                # parameter is HLH = 1 (i.e., the first column of the table).
                demand_rate = bpa_demand_rate[month_number - 1][0]  \
                                                                # bpa_demand_rate(month_number, 1)  # [$/kW (per kWh)]

                # Vertex 3: The power of Vertex 3 is the same as that of Vertex 2.
                vertices[2].power = peak_demand_threshold  # [avg.kW]

                # Vertex 3: The marginal price at Vertex 3 is shifted strongly by the demand response rate. The logic
                # here is that cost is determined by rate * (power-threshold). Therefore, the effective marginal rate is
                # augmented by the demand rate itself.
                # NOTE: Some hand-waving is always needed to compare demand and energy rates. This approach assigns a
                # meaningful production cost, but it is not correct to say it describes an energy price. The cost is
                # assigned to the entire hour. Shorter time intervals should not be further incremented. Evenso, a huge
                # discontinuity appears in the marginal price.
                vertices[2].marginalPrice = vertices[2].marginalPrice + demand_rate  # [$/kWh]

                # Evaluate the fourth of four vertices Vertex 4: The power at Vertex 4 is the maximum power, minus
                # losses.
                vertices[3].power = maximum_power - full_power_loss  # [avg.kW]

                # The marginal price at Vertex 4 is affected by both losses and demand charges.

                # Marginal price at Vertex 3 from loss component.
                vertices[3].marginalPrice = a1 * (1 + self.lossFactor)  # [$/kWh]

                # Augment marginal price at Vertex 4 with demand-charge impact.
                vertices[3].marginalPrice = vertices[3].marginalPrice + demand_rate  # [$/kW (per hour)]

                # Assign production costs for the four vertices
                # Segment 1: The second-order cost coefficient a2 on the first line segment is determined from the
                # change in marginal price divided by change in power.
                a2 = (vertices[1].marginalPrice - vertices[0].marginalPrice)  # [$/kWh]
                a2 = a2 / (vertices[1].power - vertices[0].power)  # [$/kW^2h]

                # Vertex 1: The cost at Vertex 1 can be inferred by integrating
                # from p=0 to Vertex 1.
                vertices[0].cost = a0 + a1 * vertices[0].power + 0.5 * a2 * (
                    vertices[0].power) ** 2  # production cost [$/h]

                # Vertex 2: The cost at Vertex 2 is on the same trajectory
                vertices[1].cost = a0 + a1 * vertices[1].power + 0.5 * a2 * (
                    vertices[1].power) ** 2  # production cost [$/h]

                # Vertex 3: Both the power and production cost should be the same
                # at Vertex 3 as for Vertex 2.
                vertices[2].cost = vertices[1].cost  # production cost [$/h]

                # Vertex 4: The cost on the third line segment has a new
                # trajectory that begins with the cost at Vertex 3 (an
                # integration constant).
                vertices[3].cost = vertices[2].cost  # partial production cost [#/h]

                # Segment 3: The new first-order term for the third line segment
                # is the marginal price at Vertex 3. This applies only to power
                # imports that exceed Vertex 3.
                a1 = vertices[2].marginalPrice  # first-order coefficient [$/kWh]

                # Vertex 4: Add the first-order term to the Vertex-4 cost
                vertices[3].cost = vertices[3].cost + a1 * (
                            vertices[3].power - vertices[2].power)  # partial production cost [$/h]

                # Segment 3: NOTE: The second-order coeffiecient a2 on the second
                # line segment is unchanged from the first segment

                # Vertex 4: Add the second-order term to the Vertex-4 cost.
                vertices[3].cost = vertices[3].cost + 0.5 * a2 * (
                            vertices[3].power - vertices[2].power) ** 2  # production cost [$/h]

                # Convert the costs to raw dollars
                # NOTE: This usage of Matlab hours() toggles a duration back
                # into a numerical representation, which is correct here.
                interval_duration = get_duration_in_hour(time_intervals[i].duration)

                vertices[0].cost = vertices[0].cost * interval_duration  # [$]
                vertices[1].cost = vertices[1].cost * interval_duration  # [$]
                vertices[2].cost = vertices[2].cost * interval_duration  # [$]
                vertices[3].cost = vertices[3].cost * interval_duration  # [$]

                # Create interval values for the active vertices
                interval_values = [
                    IntervalValue(self, time_intervals[i], mkt, MeasurementType.ActiveVertex, vertices[0]),
                    IntervalValue(self, time_intervals[i], mkt, MeasurementType.ActiveVertex, vertices[1]),
                    IntervalValue(self, time_intervals[i], mkt, MeasurementType.ActiveVertex, vertices[2]),
                    IntervalValue(self, time_intervals[i], mkt, MeasurementType.ActiveVertex, vertices[3])]

                # Append the active vertices to the list of active vertices
                # in the indexed time interval
                self.activeVertices.extend(interval_values)

            else:  # indexed time interval is a LLH hour
                # LLH hours
                # The indexed time interval is a LLH hour. The electricity rate
                # is a little lower, and demand charges are not applicable.
                #
                # Look up the BPA energy rate for month m. The second parameter
                # is LLH = 2 (i.e., column 2 of the table).
                energy_rate = bpa_energy_rate[month_number - 1][1]  # bpa_energy_rate(month_number, 2)

                # Two active vertices are created
                # #1 at minimum power
                # #2 at maximum power
                vertices = [Vertex(0, 0, 0), Vertex(0, 0, 0)]

                # Evaluate the first of two vertices
                # First-order parameter a1.
                a1 = energy_rate  # [$/kWh]

                # Vertex 1: Full available power transfer at Vertex 1 is thus the
                # physical transfer limit, minus losses.
                vertices[0].power = (minimum_power - minimum_power_loss)  # [avg.kW]

                # Vertex 1: Marginal price of Vertex 1 is augmented by the value
                # of energy from the neighbor that is lost. (This model assigns
                # the cost of losses to the recipient (importer) of electricity.)
                vertices[0].marginalPrice = a1 * (1 + self.lossFactor * minimum_power / maximum_power)  # [$/kWh]

                # Evaluate the second of two vertices
                # Vertex 2: The power at Vertex 2 is the maximum power, minus losses
                vertices[1].power = maximum_power - full_power_loss  # [avg.kW]

                # Vertex 2: The marginal price at Vertex 2 is affected only by
                # losses. Demand charges do not apply during LLH hours.
                #
                # Vertex 2: Marginal price at Vertex 2 from loss component
                vertices[1].marginalPrice = a1 * (1 + self.lossFactor)  # [$/kWh]

                # Assign production costs for the two vertices
                # The second-order cost coefficient a2 on the lone line segment
                # is determined from the change in marginal price divided by
                # change in power.
                a2 = (vertices[1].marginalPrice - vertices[0].marginalPrice)  # [$/kWh]
                a2 = a2 / (vertices[1].power - vertices[0].power)  # [$/kW^2h]

                # The cost at Vertex 1 can be inferred by integrating from
                # p=0 to Vertex 1.
                vertices[0].cost = a0 + a1 * vertices[0].power + 0.5 * a2 * (
                    vertices[0].power) ** 2  # production cost [$/h]

                # The cost at Vertex 2 is on the same trajectory
                vertices[1].cost = a0 + a1 * vertices[1].power + 0.5 * a2 * (
                    vertices[1].power) ** 2  # production cost [$/h]

                # Convert the costs to raw dollars
                interval_duration = get_duration_in_hour(time_intervals[i].duration)
                vertices[0].cost = vertices[0].cost * interval_duration  # [$]
                vertices[1].cost = vertices[1].cost * interval_duration  # [$]

                # Create interval values for the active vertices
                interval_values = [
                    IntervalValue(self, time_intervals[i], mkt, MeasurementType.ActiveVertex, vertices[0]),
                    IntervalValue(self, time_intervals[i], mkt, MeasurementType.ActiveVertex, vertices[1])
                ]

                # Append the active vertices to the list of active vertices
                # in the indexed time interval
                self.activeVertices.extend(interval_values)
        av = [(x.timeInterval.name, x.value.marginalPrice, x.value.power) for x in self.activeVertices]
        #_log.debug("{} bulk_supplier dc model active vertices are: {}".format(self.name, av))
