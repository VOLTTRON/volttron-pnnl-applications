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

from .vertex import Vertex
from .interval_value import IntervalValue
from .measurement_type import MeasurementType
from .helpers import *
# from market import Market
from .time_interval import TimeInterval
from .timer import Timer
from .market_state import MarketState

utils.setup_logging()
_log = logging.getLogger(__name__)

# 191218DJH: This class originally inherited from class Model. Model is being deleted. Its properties and methods are
# being moved into this class.


class LocalAsset(object):
    # A local asset model manages and represents a local asset object, meaning that it
    # (1) determines a power schedule across all active time intervals,
    # (2) calculates costs that are needed by system optimization, and
    # (3) models flexibility, if any, that is available from the control of this asset in active time intervals.
    #
    # This base class provides many of the properties and methods that will be needed to manage local assets--generation
    # and demand alike. However, it schedules only the simplest, constant power throughout active time intervals.
    # Subclassing will be required to perform dynamic power scheduling, especially where scheduling is highly
    # constrained or invokes optimizations. Even then, implementers might need further subclassing to model their unique
    # assets.
    #
    # Available subclasses that inherit from this base class: (This taxonomy is influenced by the thesis (Kok 2013).
    # Inelastic - dynamic scheduling independent of prices
    # Shiftable - schedule a fixed utility over a time range
    # Buffering - schedule power while managing a (thermal) buffer
    # Storage - optimize revenue, less cost
    # Controllable - unconstrained scheduling based on a polynomial production or utility def

    def __init__(self,
                 cost_parameters=(0.0, 0.0, 0.0),
                 default_power=0.0,
                 description='',
                 engagement_cost=(0.0, 0.0, 0.0),
                 location='',
                 maximum_power=0.0,
                 minimum_power=0.0,
                 name='',
                 # 200520DJH - The following Boolean property is added to give complex assets like TCC time to schedule
                 # their powers.
                 schedule_calculated=False,
                 scheduling_horizon=timedelta(hours=24),
                 subclass=None):

        super(LocalAsset, self).__init__()     # Inherit from any parent class

        # These following static properties may be assigned as parameters:
        self.costParameters = cost_parameters       # [float, float, float] Coefficients of quadratic cost function
        self.defaultPower = default_power           # [avg.kW, signed] Assignable default power value(s)
        self.description = description              # [text]
        self.engagementCost = engagement_cost       # {engagement, [$]; hold, [$]; disengagement, [$]} Transition costs
        self.location = location                    # [text]
        self.maximumPower = maximum_power           # [avg.kW, signed] Asset's physical "hard" constraint
        self.minimumPower = minimum_power           # [avg.kW, signed] Asset's physical "hard" constraint
        self.name = name                            # [text]
        # 200520DJH - The following Boolean property is added to give complex assets like TCC time to schedule
        # their powers.
        self.scheduleCalculated = schedule_calculated  # Flag set True after asset has scheduled power
        self.schedulingHorizon = scheduling_horizon  # [time duration] Future that price and energy shift are relevant
        self.subclass = subclass                    # Future, unused

        # These are static lists of objects that an asset must manage: These should be configured by an implementer.
        self.defaultVertices = [Vertex(float("inf"), 0.0, 1)]  # [Vertex] Default vertices; default supply/demand curve
        self.informationServices = []               # [InformationService] See class InformationService
        self.meterPoints = []                       # [MeterPoint] See class MeterPoint

        # These following properties are dynamically managed and should not normally be manually configured:
        self.activeVertices = []                    # [IntervalValue] Values are [Vertex]: Demand/Supply curves
        self.dualCosts = []                         # [IntervalValue] Values are [$]: Dual costs by interval
        self.engagementSchedule = []                # [IntervalValue] Values are [Boolean]: True = engaged
        self.productionCosts = []                   # [IntervalValue] Values are [$]: Production costs by interval
        self.reserveMargins = []                    # [IntervalValue] Values are [avg.kW, signed]
        self.scheduledPowers = []                   # [IntervalValue] Values are [avg.kW, signed]
        self.totalDualCost = 0.0                    # [$] Sum of dual costs in forward time intervals
        self.totalProductionCost = 0.0              # [$, non-negative] Sum of production costs in forward intervals
        self.transitionCosts = []                   # [IntervalValue] Values are [$]: Transition costs

    def cost(self, power=0):
        # Calculate production (consumption) cost at the given power level.
        #
        # INPUTS:
        # power - power production (consumption) for which production (consumption) costs are to be calculated [kW]. By
        #         convention, imported and generated power is positive exported or consumed power is negative.
        #
        # RETURN:
        # production_cost - calculated production (consumption) cost [$/h]
        #
        # LOCAL:
        # a - array of production cost coefficients that must be ordered [a0 a1 a2], such that
        #                              cost = a0 + a1*power + a2*power ** 2 [$/h].

        # Extract the production cost coefficients for the given object
        a = self.costParameters

        # Calculate the production (consumption) cost for the given power
        production_cost = a[0] + a[1] * power + a[2] * power ** 2  # [$/h]

        return production_cost

    # SEALED - DO NOT MODIFY
    def schedule(self, market):
        """
        Have object schedule its power in active time intervals
        :param market: Market object
        :return:
        """
        # But give power scheduling priority for a LocalAsset
        self.schedule_power(market)

        # Log if possible
        """
        if self.mtn is not None and self.power_topic != '':
            sp = [(x.timeInterval.name, x.value) for x in self.scheduledPowers]
            self.mtn.vip.pubsub.publish(peer='pubsub',
                                        topic=self.power_topic,
                                        message={'power': sp})
        """

        self.schedule_engagement(market)  # only applied to LocalAsset class

        # Update vertices and calculate reserve margins if schedule powers have been calculated
        if self.scheduleCalculated:
            self.update_vertices(market)

            # Have the objects estimate their available reserve margin.
            self.calculate_reserve_margin(market)

    def schedule_power(self, market):
        # Determine powers of an asset in active time intervals. NOTE that this method may be redefined by subclasses if
        # more features are needed. NOTE that this method name is common for all asset and neighbor models to facilitate
        # its redefinition.
        #
        # PRESUMPTIONS:
        # - Active time intervals exist and have been updated
        # - Marginal prices exist and have been updated.
        #   NOTE: Marginal prices are used only for elastic assets. This base class is provided for the simplest asset
        #         having constant power. It MUST be extended to represent dynamic and elastic asset behaviors.
        #   NOTE: (1911DJH) This requirement is loosened upon recognizing that auction markets have no forward prices
        #         available at the time an asset is called to schedule its power, i.e., to prepare its bid. This can be
        #         resolved by letting an asset model use its markets' price forecast models for forward intervals in
        #         which locational marginal prices have not yet been discovered.
        # - Transition costs, if relevant, are applied during the scheduling of assets.
        # - An engagement schedule, if used, is applied during an asset's power scheduling.
        # - Scheduled power and engagement schedule must be self consistent at the end of this method. That is, power
        #   should not be scheduled while the asset is disengaged (uncommitted).
        #
        # INPUTS:
        # market - Market object
        #
        # OUTPUTS:
        # - Updates self.scheduledPowers - the schedule of power consumed
        # - Updates self.engagementSchedule - an array that states whether the
        #   asset is engaged (committed) (true) or not (false) in the time interval

        # Gather the active time intervals ti
        time_intervals = market.timeIntervals

        # 200929DJH: This is a problem in Version 3 because it removes some perfectly valid scheduled powers in other
        #            active market objects. Commenting these lines out. Below, scheduled powers will be trimmed if they
        #            are in expired markets.
        # time_interval_values = [t.startTime for t in time_intervals]
        # self.scheduledPowers = [x for x in self.scheduledPowers if x.timeInterval.startTime in time_interval_values]

        #for power in self.scheduledPowers:
        #    _log.debug("schedule_power Market {}, time interval: {}, power value: {} ".format(power.market.name,
        #                                                                                      power.timeInterval.startTime,
        #                                                                                      power.value))

        # Sort by function lambda, assumed to be a helper function pointing to start times
        time_intervals.sort(key=lambda x: x.startTime)

        # len_powers = len(self.default_powers)
        default_value = self.defaultPower

        # Index through the active time intervals ti
        for i in range(len(time_intervals)):
            time_interval = time_intervals[i]
            # Check whether a scheduled power already exists for the indexed time interval
            iv = find_obj_by_ti(self.scheduledPowers, time_interval)

            # Reassign default value if there is power value for this time interval
            # No, no, and no. Do not assign default values apart from specific times. The real world does not always
            # begin at the same time. This method slides with the market periods, which is not correct!
            # TODO: Eliminate or fix parameter default_powers, which has been defined independent of market period.
            # if len_powers > i:
            #   default_value = self.default_powers[i] if self.default_powers[i] is not None else self.defaultPower

            if iv is None:  # A scheduled power does not exist for the indexed time interval
                #_log.debug("schedule_power Market {}, time interval: {}, iv is None".format(market.name,
                #                                                                         time_interval.startTime))
                # Create an interval value and assign the default value
                iv = IntervalValue(self, time_interval, market, MeasurementType.ScheduledPower, default_value)

                # Append the new scheduled power to the list of scheduled
                # powers for the active time intervals
                self.scheduledPowers.append(iv)

            else:
                # The scheduled power already exists for the indexed time
                # interval. Simply reassign its value
                iv.value = default_value  # [avg.kW]

        # 200929DJH: This next line prevents the list of scheduled powers from growing indefinitely.
        self.scheduledPowers = [x for x in self.scheduledPowers if x.market.marketState != MarketState.Expired]

        # sp = [(x.timeInterval.name, x.value) for x in self.scheduledPowers]
        # _log.debug("{} asset model scheduledPowers are: {}".format(self.name, sp))

    def schedule_engagement(self, market):
        # To assign engagement, or commitment, which is relevant to some local assets (supports future capabilities).
        # NOTE: The assignment of engagement schedule, if used, may be assigned during the scheduling of power, not
        # separately as demonstrated here. Commitment and engagement are closely aligned with the optimal production
        # costs of schedulable generators and utility def of engagements (e.g., demand responses).

        # NOTE: Because this is a future capability, Implementers might choose to simply return from the call until
        # LocalAsset behaviors are found to need commitment or engagement.

        # Gather the active time intervals ti
        time_intervals = market.timeIntervals  # active TimeIntervals

        # 200929DJH: This approach is too crude for Version 3 because engagement schedules are not unique to starting
        #            times. Instead, the values in expired markets will be trimmed near the bottom of this method.
        #            Commenting out offending lines.
        # time_interval_values = [t.startTime for t in time_intervals]
        # self.engagementSchedule = [x for x in self.engagementSchedule
        #                            if x.timeInterval.startTime in time_interval_values]

        # Index through the active time intervals.
        for i in range(len(time_intervals)):

            # Check whether an engagement schedule exists in the indexed time interval.
            interval_value = find_obj_by_ti(self.engagementSchedule, time_intervals[i])

            # NOTE: this template currently assigns engagement value as true (i.e., engaged).
            engagement_flag = True  # Asset is committed or engaged

            if interval_value is None:
                # No engagement schedule was found in the indexed time interval. Create an interval value and assign its
                # value as the engagement_flag.
                interval_value = IntervalValue(self, time_intervals[i], market,
                                               MeasurementType.EngagementValue, engagement_flag)

                # Append the interval value to the list of active interval values.
                self.engagementSchedule.append(interval_value)

            else:
                # An engagement schedule was found in the indexed time interval. Simply reassign its value.
                interval_value.value = engagement_flag  # [$]

        # Remove any extra engagement schedule values
        # 200929DJH: Improved to work in Version 3.
        # self.engagementSchedule = [x for x in self.engagementSchedule if x.timeInterval in ti]
        self.engagementSchedule = [x for x in self.engagementSchedule if x.market.marketState != MarketState.Expired]

    def calculate_reserve_margin(self, market):
        # Estimate available (spinning) reserve margin for this asset.
        #
        # NOTES:
        #   This method works with the simplest base classes that have constant power and therefore provide no spinning
        #   reserve. This method may be redefined by subclasses of the local asset model to add new features or
        #   capabilities.
        #   This calculation will be more meaningful and useful after resource commitments and uncertainty estimates
        #   become implemented. Until then, reserve margins may be tracked, even if they are not used.
        #
        # PRESUMPTIONS:
        # - Active time intervals exist and have been updated
        # - The asset's maximum power is a meaningful and accurate estimate of the maximum power level that can be
        #   achieved on short notice, i.e., spinning reserve.
        #
        # INPUTS:
        # market - Market object
        #
        # OUTPUTS:
        # Modifies self.reserveMargins - an array of estimated (spinning) reserve margins in active time intervals

        # Gather the active time intervals ti
        time_intervals = market.timeIntervals  # active TimeIntervals

        # 200929DJH: This approach is too crude for Version 3 and is being commented out. Instead, the reserve margins
        #            in expired markets will be removed near the bottom of this method.
        # time_interval_values = [t.startTime for t in time_intervals]
        # self.reserveMargins = [x for x in self.reserveMargins if x.timeInterval.startTime in time_interval_values]

        # Index through active time intervals ti
        for i in range(len(time_intervals)):
            # Calculate the reserve margin for the indexed interval. This is the non-negative difference between the
            # maximum asset power and the scheduled power. In principle, generation may be increased or demand decreased
            # by this quantity to act as spinning reserve.

            # Find the scheduled power in the indexed time interval
            interval_value = find_obj_by_ti(self.scheduledPowers, time_intervals[i])

            # Calculate the reserve margin in the indexed time interval. The reserve margin is the difference between
            # the maximum operational power value in the interval and the scheduled power. The operational maximum
            # should be less than the object's hard physical power constraint, so a check is in order. Start with the
            # hard physical constraint.
            hard_constraint = self.maximumPower  # [avg.kW]

            # Calculate the operational maximum constraint, which is the highest point on the supply/demand curve (i.e.,
            # the vertex) that represents the residual flexibility of the asset in the time interval.
            operational_constraint = find_objs_by_ti(self.activeVertices, time_intervals[i])

            if len(operational_constraint) == 0:

                operational_constraint = hard_constraint

            else:

                operational_constraint = [x.value for x in operational_constraint]  # active vertices
                operational_constraint = max([x.power for x in operational_constraint])  # [avg.kW]

            # Check that the upper operational power constraint is less than or equal to the object's hard physical
            # constraint.
            soft_maximum = min(hard_constraint, operational_constraint)  # [avg.kW]

            # And finally calculate the reserve margin.
            reserve_margin = max(0, soft_maximum - interval_value.value)  # [avg. kW]

            # Check whether a reserve margin already exists for the indexed time interval
            interval_value = find_obj_by_ti(self.reserveMargins, time_intervals[i])  # an IntervalValue

            if interval_value is None:

                # A reserve margin does not exist for the indexed time interval. Create it. (See IntervalValue class.)
                interval_value = IntervalValue(self, time_intervals[i], market,
                                               MeasurementType.ReserveMargin, reserve_margin)

                # Append the new reserve margin interval value to the list of reserve margins for the active time
                # intervals.
                self.reserveMargins.append(interval_value)

            else:
                # The reserve margin already exists for the indexed time interval. Simply reassign its value.
                interval_value.value = reserve_margin  # [avg.kW]

        # 200929DJH: Remove any reserve margins that lie in expired markets.
        self.reserveMargins = [x for x in self.reserveMargins if x.market.marketState != MarketState.Expired]

    def engagement_cost(self, dif):
        # Assigns engagement cost based on difference in engagement status in the current minus prior time intervals.
        #
        # INPUTS:
        # dif - difference (current interval engagement - prior interval engagement), which assumes integer values
        #       [-1,0,1] that should correspond to the three engagement costs.
        # USES:
        # self.engagementSchedule
        # self.engagementCost
        #
        # OUTPUTS:
        # cost - transition cost
        # diff - cost table as a def of current and prior engagement states:
        #    \  current |   false   |  true
        # prior false   |  0:ec(2)  | 1:ec(3)
        #       true    | -1:ec(1)  | 0:ec(2)

        # Check that dif is a feasible difference between two logical values
        if dif not in [-1, 0, 1]:
            print('Input value must be in the set {-1,0,1}.')
            cost = None
            return cost

        # Assign engagement cost by indexing the three values of engagement cost
        # 1 - transition from false to true - engagement cost
        # 2 - no change in engagement - no cost
        # 3 - transition from true to false - disengagement cost
        cost = self.engagementCost[1 + dif]

        return cost

    def assign_transition_costs(self, market):
        # Assign the cost of changing engagement state from the prior to the current time interval
        #
        # PRESUMPTIONS:
        # - Time intervals exist and have been updated
        # - The engagement schedule exists and has been updated. Contents are logical [true/false].
        # - Engagement costs have been accurately assigned for [disengagement, unchanged, engagement]
        #
        # INPUTS:
        # market - Market object
        #
        # USES:
        # - self.engagementCost - three costs that correspond to [disengagement, unchanged, engagement) transitions
        # - self.engagement_cost() - assigns appropriate cost from self.engagementCost property
        # - self.engagementSchedule - engagement states (true/false) for the asset in active time intervals
        #
        # OUTPUTS:
        # Assigns values to self.transition_costs

        # Gather active time intervals
        time_intervals = market.timeIntervals

        # 200929DJH: This method for trimming the transition costs is too crude for Version 3. Commenting out. Instead,
        #            the transaction costs that lie in expired markets will be trimmed further down.
        # time_interval_values = [t.startTime for t in time_intervals]
        # self.transitionCosts = [x for x in self.transitionCosts if x.timeInterval.startTime in time_interval_values]

        # Ensure that ti is ordered by time interval start times
        time_intervals.sort(key=lambda x: x.startTime)

        # Index through all but the first time interval.
        for i in range(len(time_intervals)):

            # Find the current engagement schedule ces in the current indexed time interval ti(i)
            # 200929DJH: In Version 3, the engagement state must be matched to a time interval object, not its start
            #            time, which is not necessarily unique.
            # current_engagement_state = [x for x in self.engagementSchedule
            #                             if x.timeInterval.startTime == time_intervals[i].startTime]
            current_engagement_state = [x.value for x in self.engagementSchedule if x.timeInterval == time_intervals[i]]

            # TODO: The calculation of transition cost is not right for the first time interval (being compared to last)
            # TODO: This calculation can probably be vectorized when time permits to speed it up.
            # Find the engagement state from in the prior indexed time interval (i-1).
            # 200929DJH: As above, make selection based on time interval object, not its start time, which may not be
            #            unique.
            # prior_engagement_state = [x for x in self.engagementSchedule
            #                           if x.timeInterval.startTime == time_intervals[i - 1].startTime]
            prior_engagement_state = [x.value for x in self.engagementSchedule
                                      if x.timeInterval == time_intervals[i - 1]]

            # Calculate the state transition
            # - -1:Disengaging
            # -  0:Unchanged
            # -  1:Engaging
            dif = current_engagement_state - prior_engagement_state

            # Assign the corresponding transition cost
            transition_cost = self.engagement_cost(dif)

            # Check whether a transition cost exists in the indexed time interval
            interval_value = find_obj_by_ti(self.transitionCosts, time_intervals[i])

            if interval_value is None:

                # No transition cost was found in the indexed time interval. Create an interval value and assign its
                # value.
                interval_value = IntervalValue(self, time_intervals[i], market,
                                               MeasurementType.TransitionCost, transition_cost)

                # Append the interval value to the list of active interval values
                self.transitionCosts.append(interval_value)

            else:

                # A transition cost was found in the indexed time interval. Simply reassign its value.
                interval_value.value = transition_cost  # [$]

        # 200929DJH: Trim any transition costs that lie in expired markets.
        self.transitionCosts = [x for x in self.transitionCosts if x.market.marketState != MarketState.Expired]

        # Remove any extraneous transition cost values
        # self.transitionCosts = [x for x in self.transitionCosts if x.timeInterval in time_intervals]

    def update_dual_costs(self, market):
        # Update the dual cost for all active time intervals
        # (NOTE: Choosing not to separate this def from the base class because cost might need to be handled differently
        # and redefined in subclasses.)

        # Gather the active time intervals.
        time_intervals = market.timeIntervals

        # Index through the time intervals.
        # NOTE 1911DJH: The range in this for-loop has been corrected and now passes unit testing. I believe the code
        # had been modified to avoid revising the schedule for the first hour in Version 2. This is corrected by the
        # market state transition model in Version 3, which should be configured to NOT allow negotiation of prices and
        # quantities after the respective market has cleared or entered its delivery period.
        for i in range(len(time_intervals)):

            # Find the marginal price mp for the indexed time interval ti(i) in the given market.
            marginal_price = find_obj_by_ti(market.marginalPrices, time_intervals[i])
            marginal_price = marginal_price.value  # a marginal price [$/kWh]

            # Find the scheduled power sp for the asset in the indexed time interval i.
            scheduled_power = find_obj_by_ti(self.scheduledPowers, time_intervals[i])
            scheduled_power = scheduled_power.value  # [avg.kW]

            # Find the production cost in the indexed time interval.
            production_cost = find_obj_by_ti(self.productionCosts, time_intervals[i])
            production_cost = production_cost.value  # [$]

            # Dual cost in the time interval is calculated as production cost, minus the product of marginal price,
            # scheduled power, and the duration of the time interval.
            duration = time_intervals[i].duration.seconds // 3600
            dual_cost = production_cost - (marginal_price * scheduled_power * duration)  # [$]

            # Check whether a dual cost exists in the indexed time interval
            interval_value = find_obj_by_ti(self.dualCosts, time_intervals[i])

            if interval_value is None:

                # No dual cost was found in the indexed time interval. Create an interval value and assign it the
                # calculated value.
                interval_value = IntervalValue(self, time_intervals[i], market, MeasurementType.DualCost, dual_cost)

                # Append the new interval value to the list of active interval values.
                self.dualCosts.append(interval_value)

            else:

                # The dual cost value was found to already exist in the indexed time interval. Simply reassign it the
                # new calculated value.
                interval_value.value = dual_cost  # [$]

        # Ensure that only active time intervals are in the list of dual costs
        # self.dualCosts = [x for x in self.dualCosts if x.timeInterval in ti]
        # 200929DJH: Trim dual costs that lie in expired markets.
        self.dualCosts = [x for x in self.dualCosts if x.market.marketState != MarketState.Expired]

        # Sum the total dual cost and save the value.
        # 200929DJH: This is corrected to sum only the dual costs in the current market
        self.totalDualCost = sum([x.value for x in self.dualCosts if x.market == market])

        dual_cost = [(x.timeInterval.name, x.value) for x in self.dualCosts]
        #        _log.debug("{} asset model dual costs are: {}".format(self.name, dc))

    def update_production_costs(self, market):
        # Calculate the costs of generated energies.
        # (NOTE: Choosing not to separate this def from the base class because cost might need to be handled differently
        # and redefined in subclasses.)

        # Gather active time intervals.
        time_intervals = market.timeIntervals

        # Index through the active time intervals.
        for i in range(len(time_intervals)):

            # Get the scheduled power in the indexed time interval.
            scheduled_power = find_obj_by_ti(self.scheduledPowers, time_intervals[i])
            scheduled_power = scheduled_power.value  # schedule power [avg.kW]

            # Call on def that calculates production cost pc based on the vertices of the supply or demand curve
            # NOTE that this def is now stand-alone because it might be generally useful for a number of models.
            production_cost = prod_cost_from_vertices(self, time_intervals[i], scheduled_power)  # [$]

            # Check for a transition cost in the indexed time interval.
            # (NOTE: this differs from neighbor models, which do not posses the concept of commitment and engagement.
            # This is a good reason to keep this method within its base class to allow for subtle differences.)
            transition_cost = find_obj_by_ti(self.transitionCosts, time_intervals[i])

            if transition_cost is None:
                transition_cost = 0.0  # [$]
            else:
                transition_cost = transition_cost.value  # [$]

            # Add the transition cost to the production cost
            production_cost = production_cost + transition_cost

            # Check to see if the production cost value has been defined for the indexed time interval
            interval_value = find_obj_by_ti(self.productionCosts, time_intervals[i])

            if interval_value is None:

                # The production cost value has not been defined in the indexed time interval. Create it and assign its
                # value.
                interval_value = IntervalValue(self, time_intervals[i], market,
                                               MeasurementType.ProductionCost, production_cost)

                # Append the production cost to the list of active production cost values
                self.productionCosts.append(interval_value)  #

            else:

                # The production cost value already exists in the indexed time interval. Simply reassign its value.
                interval_value.value = production_cost  # [$]

        # Ensure that only active time intervals are in the list of active production costs.
        # 200929DJH: This must be corrected in Version 3 because there are perfectly valid production costs in other
        #            markets. Instead, trim the production costs that lie in expired markets.
        # self.productionCosts = [x for x in self.productionCosts if x.timeInterval in time_intervals]
        self.productionCosts = [x for x in self.productionCosts if x.market.marketState != MarketState.Expired]

        # Sum the total production cost.
        # 200929DJH: In Version 3, this sum must be made only within the current market object.
        # self.totalProductionCost = sum([x.value for x in self.productionCosts])  # total production cost [$]
        self.totalProductionCost = sum([x.value for x in self.productionCosts if x.market == market])  # [$]

        production_cost = [(x.timeInterval.name, x.value) for x in self.productionCosts]
        # _log.debug("{} asset model production costs are: {}".format(self.name, pc))

    def update_vertices(self, market):
        # Create vertices to represent the asset's flexibility
        #
        # For the base local asset model, a single, inelastic power is needed. There is no flexibility. The constant
        # power may be represented by a single (price, power) point (See struct Vertex).

        # Gather active time intervals.
        time_intervals = market.timeIntervals  # active TimeIntervals

        '''
        for power in self.scheduledPowers:
            _log.debug("update_vertices Market {}, time interval: {}, power value: {} ".format(power.market.name,
                                                                                              power.timeInterval.startTime,
                                                                                              power.value))
        _log.debug("update_vertices Market: {}, scheduled powers: {}".format(market.name,
                                                                            self.scheduledPowers))
        '''

        # Index through active time intervals.
        for i in range(len(time_intervals)):

            # Find the scheduled power for the indexed time interval. Extract the scheduled power value.
            # TODO: Make this next line tolerant upon finding scheduled_power = None.
            scheduled_power = find_obj_by_ti(self.scheduledPowers, time_intervals[i])
            scheduled_power = scheduled_power.value  # avg. kW]

            # Create the vertex that can represent this (lack of) flexibility
            value = Vertex(float("inf"), 0.0, scheduled_power, True)

            # Check to see if the active vertex already exists for this indexed time interval.
            interval_value = find_obj_by_ti(self.activeVertices, time_intervals[i])

            # If the active vertex does not exist, a new interval value must be created and stored.
            if interval_value is None:

                # Create the interval value and place the active vertex in it
                interval_value = IntervalValue(self, time_intervals[i], market, MeasurementType.ActiveVertex, value)

                # Append the interval value to the list of active vertices.
                self.activeVertices.append(interval_value)

            else:

                # Otherwise, simply reassign the active vertex value to the existing listed interval value.
                # NOTE that this base local asset model unnecessarily reassigns constant values, but the reassignment
                # is allowed because it teaches how a more dynamic assignment may be maintained.
                interval_value.value = value

        # 200929DJH: Trim the list of active vertices so that it will not grow indefinitely.
        self.activeVertices = [x for x in self.activeVertices if x.market.marketState != MarketState.Expired]

        av = [(x.timeInterval.name, x.value.marginalPrice, x.value.power) for x in self.activeVertices]
        #_log.debug("{} asset model active vertices are: {}".format(self.name, av))

    def get_extended_prices(self, market):  # 200120DJH This does not, after all, require a TransactiveNode parameter.
        """
        This method is available to facilitate estimation of opportunity cost for local assets that have a scheduling
        horizon that extends farther into the future than supplied by the market in forward time intervals. For example,
        a market may offer only one forward time interval with its price offer. Even in this example, auction markets do
        not provide market prices at the times bids are to be formulated by the local asset. Local assets having states
        (e.g., controlled interior temperature, battery charge state) must some how calibrate prices farther into the
        future as a foundation for understanding the opportunity cost.
        This base method uses the following prioritization to populate the price horizon:
        1. Actual marginal prices offered by the market object.
        2. Actual marginal prices in prior sequential markets that are similar to the market object.
        3. Actual marginal prices in prior markets that are being corrected by the market object.
        4. Modeled prices using the market's price model
        5. The market's default price value.
        6. Nothing
        NOTE: This method is similar to Market.check_marginal_prices(), but that method's purpose is to specifically
              estimate marginal prices for active time intervals, not throughout the scheduling horizon.
        :param market: Market object that these prices are relevant to
        :param this_transactive_node: TransactiveNode object that represents the local transactive agent
        :return: price_horizon, which may be placed into property self.schedulingHorizon by caller
        """

        # The scheduling horizon is a distance into the future. The price horizon is initialized, then prices are found
        # from now until the end of the scheduling horizon.
        # TODO: Check that this usage of Timer() is consistent with campus simulation process
        price_horizon = []
        end_of_calculated_horizon = Timer.get_cur_time()
        end_of_scheduling_horizon = end_of_calculated_horizon + self.schedulingHorizon

        # Case 1: Actual marginal prices offered by the market object that has requested the asset to schedule.

        # Get the existing marginal prices from the current market object:
        market_prices = market.marginalPrices

        if not isinstance(market_prices, type(None)) and market_prices is not None:
            if isinstance(market_prices, list) and len(market_prices) != 0:
                price_horizon.extend(market_prices)

                end_of_calculated_horizon = price_horizon[0].timeInterval.startTime + market.intervalDuration
                for x in range(1, len(market_prices)):
                    end_time = price_horizon[x].timeInterval.startTime + market.intervalDuration
                    if end_time > end_of_calculated_horizon:
                        end_of_calculated_horizon = end_time

                if end_of_calculated_horizon >= end_of_scheduling_horizon:
                    return price_horizon

        # Case 2: Actual marginal prices in prior sequential markets that are similar to the market object.
        # 191212DJH: This logic is greatly simplified by introducing the pointer priorMarketInSeries.
        if not isinstance(market.priorMarketInSeries, type(None)) and market.priorMarketInSeries is not None:

            prior_market_in_series = market.priorMarketInSeries

            # Get the marginal prices from the latest similar market.
            market_prices = prior_market_in_series.marginalPrices

            if not isinstance(market_prices, type(None)) and market_prices is not None:
                if isinstance(market_prices, list) and len(market_prices) != 0:

                    # Find any market prices from the corrected market to add to the price horizon
                    for x in range(len(market_prices)):
                        interval_end_time = market_prices[x].timeInterval.startTime \
                                            + market_prices[x].market.intervalDuration
                        if interval_end_time > end_of_calculated_horizon:
                            price_horizon.append(market_prices[x])

                    # Find the end of the calculated price horizon
                    for x in range(len(price_horizon)):
                        end_time = price_horizon[x].timeInterval.startTime \
                                   + price_horizon[x].market.intervalDuration
                        if end_time > end_of_calculated_horizon:
                            end_of_calculated_horizon = end_time

                    if end_of_calculated_horizon >= end_of_scheduling_horizon:
                        return price_horizon

        # Case 3. Actual marginal prices in prior markets that are being corrected by the market object.
        # Start by gathering similar prior markets that are in the market series being corrected
        # 191212DJH: This logic is simplified by introduction of pointer priorRefinedMarket
        if not isinstance(market.priorRefinedMarket, type(None)) and market.priorRefinedMarket is not None:

            prior_refined_market = market.priorRefinedMarket

            # Get the marginal prices from the latest similar market.
            market_prices = prior_refined_market.marginalPrices

            if not isinstance(market_prices, type(None)) and market_prices is not None:

                if isinstance(market_prices, list) and len(market_prices) != 0:

                    # Find any market prices from the corrected market to add to the price horizon
                    # TODO: This following logic might be sensitive to order of prices found
                    for x in range(len(market_prices)):
                        interval_end_time = market_prices[x].timeInterval.startTime \
                                            + market_prices[x].market.intervalDuration
                        if interval_end_time > end_of_calculated_horizon:
                            price_horizon.append(market_prices[x])

                    # Find the end of the calculated price horizon
                    for x in range(len(price_horizon)):
                        end_time = price_horizon[x].timeInterval.startTime \
                                   + price_horizon[x].market.intervalDuration
                        if end_time > end_of_calculated_horizon:
                            end_of_calculated_horizon = end_time

                    if end_of_calculated_horizon >= end_of_scheduling_horizon:
                        return price_horizon

        # Case 4. Modeled prices using the market's price model
        market_prices = []
        if market.priceModel is not None:
            while end_of_scheduling_horizon > end_of_calculated_horizon:
                price = market.model_prices(end_of_calculated_horizon)
                start_time = end_of_calculated_horizon.replace(minute=0, second=0)
                end_time = start_time + timedelta(hours=1)
                duration = end_time - start_time
                ti = TimeInterval(Timer.get_cur_time(), duration, market,
                                  market.marketClearingTime, start_time)
                iv = IntervalValue(self, ti, market, None, price[0])
                market_prices.append(iv)
                end_of_calculated_horizon = end_time

            if type(market_prices) is list and len(market_prices) > 0:
                price_horizon.extend(market_prices)

            return price_horizon

        # Case 5. The market's default price value.
        # 191231DJH: This case presumes hour-long intervals.
        market_prices = []
        price = market.defaultPrice
        while end_of_scheduling_horizon > end_of_calculated_horizon:
            start_time = end_of_calculated_horizon
            end_time = start_time + timedelta(hours=1)
            end_time.replace(minute=0, second=0, microsecond=0)
            duration = end_time - start_time
            ti = TimeInterval(Timer.get_cur_time(), duration, market,
                              market.marketClearingTime, start_time)
            iv = IntervalValue(self, ti, market, MeasurementType.MarginalPrice, price)
            price_horizon.append(iv)
            end_of_calculated_horizon = end_time

        return price_horizon

    def update_costs(self, market):
        """
        191218DJH: This method was originally inherited from class (Abstract)Model. The purpose was to prescribe the set
        of cost calculation that every asset (and neighbor) must perform. The class structure is being simplified. Class
        Model is being deleted, and its properties and methods are being moved to its children.
        :param market:
        :return:
        """

        # Initialize sums of production and dual costs.
        self.totalProductionCost = 0.0
        self.totalDualCost = 0.0

        # Have object update and store its production and dual costs in each active time interval.
        self.update_production_costs(market)
        self.update_dual_costs(market)

        # Sum total production and dual costs through all time intervals.
        self.totalProductionCost = sum([x.value for x in self.productionCosts])
        self.totalDualCost = sum([x.value for x in self.dualCosts])

    def getDict(self):
        scheduled_powers = [(utils.format_timestamp(x.timeInterval.startTime), x.value) for x in self.scheduledPowers]
        vertices = [(utils.format_timestamp(x.timeInterval.startTime), x.value.marginalPrice, x.value.power) for x in self.activeVertices]
        local_asset_dict = {
            "name": self.name,
            "scheduled_power": scheduled_powers,
            "vertices": vertices
        }
        return local_asset_dict
