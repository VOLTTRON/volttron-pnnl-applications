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

from .model import Model
from .vertex import Vertex
from .interval_value import IntervalValue
from .measurement_type import MeasurementType
from .helpers import *
from .market import Market
from .time_interval import TimeInterval
from .local_asset import LocalAsset

utils.setup_logging()
_log = logging.getLogger(__name__)


class LocalAssetModel(Model, object):
    # A local asset model manages and represents a local asset object,
    # meaning that it
    # (1) determines a power schedule across all active time intervals,
    # (2) calculates costs that are needed by system optimization, and
    # (3) models flexibility, if any, that is available from the control of
    # this asset in active time intervals.
    #
    # This base class provides many of the properties and methods that will
    # be needed to manage local assets--generation and demand alike. However,
    # it schedules only the simplest, constant power throughout active time
    # intervals. Subclassing will be required to perform dynamic power
    # scheduling, expecially where scheduling is highly constrained or
    # invokes optimizations. Even then, implementers might need further
    # subclassing to model their unique assets.
    #
    # Available subclasses that inherit from this base class: (This taxonomy
    # is influenced by the thesis (Kok 2013).
    # Inelastic - dynamic scheduling independent of prices
    # Shiftable - schedule a fixed utility over a time range
    # Buffering - schedule power while managing a (thermal) buffer
    # Storage - optimize revenue, less cost
    # Controllable - unconstrained scheduling based on a polynomial production or utility def

    def __init__(self):
        super(LocalAssetModel, self).__init__()
        self.engagementCost = [0.0, 0.0, 0.0]  # [engagement, hold, disengagement][$]
        self.engagementSchedule = []  # IntervalValue.empty
        self.informationServices = []  # InformationService.empty
        self.transitionCosts = []  # IntervalValue.empty  # values are [$]

        # Default power values for each time interval
        self.default_powers = []
        # Default power value for intervals that are not in default_powers[avg. kW]
        # Need to be set when using object
        self.defaultPower = 0.0

        self.totalDualCost = 0.0
        self.totalProductionCost = 0.0

    def cost(self, p):
        # Calculate production (consumption) cost at the given power level.
        #
        # INPUTS:
        # obj - class object for which the production costs are to be
        # calculated
        # p - power production (consumption) for which production
        # (consumption) costs are to be calculated [kW]. By convention,
        # imported and generated power is positive exported or consumed
        # power is negative.
        #
        # OUTPUTS:
        # pc - calculated production (consumption) cost [$/h]
        #
        # LOCAL:
        # a - array of production cost coefficients that must be ordered [a0
        # a1 a2], such that cost = a0 + a1*p + a2*p^2 [$/h].
        # *************************************************************************

        # Extract the production cost coefficients for the given object

        a = self.cost_parameters

        # Calculate the production (consumption) cost for the given power

        pc = a[0] + a[1] * p + a[2] * p ^ 2  # [$/h]

        return pc

    ## SEALED - DONOT MODIFY
    def schedule(self, mkt):
        """
        Have object schedule its power in active time intervals
        :param mkt:
        :return:
        """
        # But give power scheduling priority for a LocalAssetModel
        self.schedule_power(mkt)
        # Log if possible
        if self.mtn is not None and self.power_topic != '':
            sp = [(x.timeInterval.name, x.value) for x in self.scheduledPowers]
            self.mtn.vip.pubsub.publish(peer='pubsub',
                                        topic=self.power_topic,
                                        message={'power': sp})

        self.schedule_engagement(mkt)  # only LocalAssetModels
        self.update_vertices(mkt)

        # Have the objects estimate their available reserve margin
        self.calculate_reserve_margin(mkt)

    def schedule_power(self, mkt):
        # Determine powers of an asset in active time
        # intervals. NOTE that this method may be redefined by subclasses if more
        # features are needed. NOTE that this method name is common for all asset
        # and neighbor models to facilitate its redefinition.
        #
        # PRESUMPTIONS:
        # - Active time intervals exist and have been updated
        # - Marginal prices exist and have been updated. NOTE: Marginal prices
        #   are not used for inelastic assets.
        # - Transition costs, if relevant, are applied during the scheduling
        #   of assets.
        # - An engagement schedule, if used, is applied during an asset's power
        #   scheduling.
        # - Scheduled power and engagement schedule must be self consistent at
        # the end of this method. That is, power should not be scheduled while
        # the asset is disengaged (uncommitted).
        #
        # INPUTS:
        # mkt - market object
        #
        # OUTPUTS:
        # - Updates self.scheduledPowers - the schedule of power consumed
        # - Updates self.engagementSchedule - an array that states whether the
        #   asset is engaged (committed) (true) or not (false) in the time interval

        # Gather the active time intervals ti
        time_intervals = mkt.timeIntervals
        time_interval_values = [t.startTime for t in time_intervals]
        self.scheduledPowers = [x for x in self.scheduledPowers if x.timeInterval.startTime in time_interval_values]

        time_intervals.sort(key=lambda x: x.startTime)

        len_powers = len(self.default_powers)
        default_value = self.defaultPower

        # Index through the active time intervals ti
        for i in range(len(time_intervals)):
            # Check whether a scheduled power already exists for the indexed time interval
            iv = find_obj_by_ti(self.scheduledPowers, time_intervals[i])

            # Reassign default value if there is power value for this time interval
            if len_powers > i:
                default_value = self.default_powers[i] if self.default_powers[i] is not None else self.defaultPower

            if iv is None:  # A scheduled power does not exist for the indexed time interval
                # Create an interval value and assign the default value
                iv = IntervalValue(self, time_intervals[i], mkt, MeasurementType.ScheduledPower, default_value)

                # Append the new scheduled power to the list of scheduled
                # powers for the active time intervals
                self.scheduledPowers.append(iv)

            else:
                # The scheduled power already exists for the indexed time
                # interval. Simply reassign its value
                iv.value = default_value  # [avg.kW]

        sp = [(x.timeInterval.name, x.value) for x in self.scheduledPowers]
        _log.debug("{} asset model scheduledPowers are: {}".format(self.name, sp))

    def schedule_engagement(self, mkt):
        # To assign engagement, or commitment, which
        # is relevant to some local assets (supports future capabilities).
        # NOTE: The assignment of engagement schedule, if used, may be assigned
        # during the scheduling of power, not separately as demonstrated here.
        # Commitment and engagement are closely aligned with the optimal
        # production costs of schedulable generators and utility def of
        # engagements (e.g., demand responses).

        # NOTE: Because this is a future capability, Implementers might choose to
        # simply return from the call until LocalAsset behaviors are found to need
        # commitment or engagement.

        # Gather the active time intervals ti
        time_intervals = mkt.timeIntervals  # active TimeIntervals
        time_interval_values = [t.startTime for t in time_intervals]
        self.engagementSchedule = [x for x in self.engagementSchedule if x.timeInterval.startTime in time_interval_values]

        # Index through the active time intervals ti
        for i in range(len(time_intervals)):
            # Check whether an engagement schedule exists in the indexed time interval
            iv = find_obj_by_ti(self.engagementSchedule, time_intervals[i])

            # NOTE: this template currently assigns engagement value as true (i.e., engaged).
            val = True  # Asset is committed or engaged

            if iv is None:
                # No engagement schedule was found in the indexed time interval.
                # Create an interval value and assign its value.
                iv = IntervalValue(self, time_intervals[i], mkt, MeasurementType.EngagementValue, val)  # an IntervalValue

                # Append the interval value to the list of active interval values
                self.engagementSchedule.append(iv)

            else:
                # An engagement schedule was found in the indexed time interval.
                # Simpy reassign its value.
                iv.value = val  # [$]

        # Remove any extra engagement schedule values
        #self.engagementSchedule = [x for x in self.engagementSchedule if x.timeInterval in ti]

    def calculate_reserve_margin(self, mkt):
        # Estimate available (spinning) reserve margin for this asset.
        #
        # NOTES:
        #   This method works with the simplest base classes that have constant
        #   power and therefore provide no spinning reserve. This method may be
        #   redefined by subclasses of the local asset model to add new features
        #   or capabilities.
        #   This calculation will be more meaningful and useful after resource
        #   commitments and uncertainty estimates become implemented. Until then,
        #   reserve margins may be tracked, even if they are not used.
        #
        # PRESUMPTIONS:
        # - Active time intervals exist and have been updated
        # - The asset's maximum power is a meaningful and accurate estimate of
        #   the maximum power level that can be achieved on short notice, i.e.,
        #   spinning reserve.
        #
        # INPUTS:
        # mkt - market object
        #
        # OUTPUTS:
        # Modifies self.reserveMargins - an array of estimated (spinning) reserve
        # margins in active time intervals

        # Gather the active time intervals ti
        time_intervals = mkt.timeIntervals  # active TimeIntervals
        time_interval_values = [t.startTime for t in time_intervals]
        self.reserveMargins = [x for x in self.reserveMargins if x.timeInterval.startTime in time_interval_values]

        # Index through active time intervals ti
        for i in range(len(time_intervals)):
            # Calculate the reserve margin for the indexed interval. This is the
            # non-negative difference between the maximum asset power and the
            # scheduled power. In principle, generation may be increased or
            # demand decreased by this quantity to act as spinning reserve.

            # Find the scheduled power in the indexed time interval
            iv = find_obj_by_ti(self.scheduledPowers, time_intervals[i])

            # Calculate the reserve margin rm in the indexed time interval. The
            # reserve margin is the differnce between the maximum operational
            # power value in the interval and the scheduled power. The
            # operational maximum should be less than the object's hard physical
            # power constraint, so a check is in order.
            # start with the hard physical constraint.
            hard_const = self.object.maximumPower  # [avg.kW]

            # Calculate the operational maximum constraint, which is the highest
            # point on the supply/demand curve (i.e., the vertex) that represents
            # the residual flexibility of the asset in the time interval.
            op_const = find_objs_by_ti(self.activeVertices, time_intervals[i])

            if len(op_const) == 0:
                op_const = hard_const
            else:
                op_const = [x.value for x in op_const]  # active vertices
                op_const = max([x.power for x in op_const])  # operational max. power[avg.kW]

            # Check that the upper operational power constraint is less than or
            # equal to the object's hard physical constraint.
            soft_maximum = min(hard_const, op_const)  # [avg.kW]

            # And finally calculate the reserve margin.
            rm = max(0, soft_maximum - iv.value)  # reserve margin [avg. kW]

            # Check whether a reserve margin already exists for the indexed time interval
            iv = find_obj_by_ti(self.reserveMargins, time_intervals[i])  # an IntervalValue

            if iv is None:
                # A reserve margin does not exist for the indexed time interval.
                # create it. (See IntervalValue class.)
                iv = IntervalValue(self, time_intervals[i], mkt, MeasurementType.ReserveMargin, rm)  # an IntervalValue

                # Append the new reserve margin interval value to the list of
                # reserve margins for the active time intervals
                self.reserveMargins.append(iv)

            else:
                # The reserve margin already exists for the indexed time
                # interval. Simply reassign its value.
                iv.value = rm  # reserve margin [avg.kW]

    def engagement_cost(self, dif):
        # Assigns engagement cost based on difference
        # in engagement status in the current minus prior time intervals.
        #
        # INPUTS:
        # dif - difference (current interval engagement - prior interval
        #  engagement), which assumes integer values [-1,0,1] that should
        #  correspond to the three engagement costs.
        # USES:
        # self.engagementSchedule
        # self.engagementCost
        #
        # OUTPUTS:
        # cost - transition cost
        # diff - cost table as a def of current and prior engagement states:
        #   \ current |   false   |  true
        # prior false   |  0:ec(2)  | 1:ec(3)
        # true    | -1:ec(1)  | 0:ec(2)

        # Check that dif is a feasible difference between two logical values
        if dif not in [-1, 0, 1]:
            print('Input value must be in the set {-1,0,1}.')
            return

        # Assign engagement cost by indexing the three values of engagement cost
        # 1 - transition from false to true - engagement cost
        # 2 - no change in engagemment - no cost
        # 3 - transition from true to false - disengagment cost
        cost = self.engagementCost[1 + dif]

        return cost

    def assign_transition_costs(self, mkt):
        # Assign the cost of changeing
        # engagement state from the prior to the current time interval
        #
        # PRESUMPTIONS:
        # - Time intervals exist and have been updated
        # - The engagement schedule exists and has been updated. Contents are
        #   logical [true/false].
        # - Engagement costs have been accurately assigned for [disengagement,
        #   unchanged, engagement]
        #
        # INPUTS:
        # mkt - Market object
        #
        # USES:
        # - self.engagementCost - three costs that correspond to
        #   [disengagement, unchanged, engagement) transitions
        # - self.engagement_cost() - assigns appropriate cost from
        #   self.engagementCost property
        # - self.engagementSchedule - engagement states (true/false) for the asset
        #   in active time intervals
        #
        # OUTPUTS:
        # Assigns values to self.transition_costs

        # Gather active time intervals
        time_intervals = mkt.timeIntervals
        time_interval_values = [t.startTime for t in time_intervals]
        self.transitionCosts = [x for x in self.transitionCosts if x.timeInterval.startTime in time_interval_values]

        # Ensure that ti is ordered by time interval start times
        time_intervals.sort(key=lambda x: x.startTime)

        # Index through all but the first time interval ti
        for i in range(len(time_intervals)):
            # Find the current engagement schedule ces in the current indexed
            # time interval ti(i)
            ces = [x for x in self.engagementSchedule if x.timeInterval.startTime == time_intervals[i].startTime]

            # Extract its engagement state
            ces = ces[0].value  # logical (true/false)

            # Find the engagement schedule pes in the prior indexed time interval ti(i-1)
            pes = [x for x in self.engagementSchedule if x.timeInterval.startTime == time_intervals[i - 1].startTime]

            # And extract its value
            pes = pes[0].value  # logical (true/false)

            # Calculate the state transition
            # - -1:Disengaging
            # -  0:Unchaged
            # -  1:Engaging
            dif = ces - pes

            # Assign the corresponding transition cost
            val = self.engagement_cost(dif)

            # Check whether a transition cost exists in the indexed time interval
            iv = find_obj_by_ti(self.transitionCosts, time_intervals[i])

            if iv is None:
                # No transition cost was found in the indexed time interval.
                # Create an interval value and assign its value.
                iv = IntervalValue(self, time_intervals[i], mkt, MeasurementType.TransitionCost, val)

                # Append the interval value to the list of active interval values
                self.transitionCosts.append(iv)

            else:
                # A transition cost was found in the indexed time interval.
                # Simpy reassign its value.
                iv.value = val  # [$]

        # Remove any extraneous transition cost values
        #self.transitionCosts = [x for x in self.transitionCosts if x.timeInterval in time_intervals]

    def update_dual_costs(self, mkt):
        # Update the dual cost for all active time intervals
        # (NOTE: Choosing not to separate this def from the base class because
        # cost might need to be handled differently and redefined in subclasses.)

        # Gather the active time intervals ti
        time_intervals = mkt.timeIntervals
        time_interval_values = [t.startTime for t in time_intervals]
        self.dualCosts = [x for x in self.dualCosts if x.timeInterval.startTime in time_interval_values]

        # Index through the time intervals ti
        for i in range(1, len(time_intervals)):
            # Find the marginal price mp for the indexed time interval ti(i) in
            # the given market mkt
            mp = find_obj_by_ti(mkt.marginalPrices, time_intervals[i])
            mp = mp.value  # a marginal price [$/kWh]

            # Find the scheduled power sp for the asset in the indexed time interval ti(i)
            sp = find_obj_by_ti(self.scheduledPowers, time_intervals[i])
            sp = sp.value  # schedule power [avg.kW]

            # Find the production cost in the indexed time interval
            pc = find_obj_by_ti(self.productionCosts, time_intervals[i])
            pc = pc.value  # production cost [$]

            # Dual cost in the time interval is calculated as production cost,
            # minus the product of marginal price, scheduled power, and the
            # duration of the time interval.
            dur = time_intervals[i].duration.seconds // 3600
            dc = pc - (mp * sp * dur)  # a dual cost [$]

            # Check whether a dual cost exists in the indexed time interval
            iv = find_obj_by_ti(self.dualCosts, time_intervals[i])

            if iv is None:
                # No dual cost was found in the indexed time interval. Create an
                # interval value and assign it the calculated value.
                iv = IntervalValue(self, time_intervals[i], mkt, MeasurementType.DualCost, dc)

                # Append the new interval value to the list of active interval values
                self.dualCosts.append(iv)

            else:
                # The dual cost value was found to already exist in the indexed
                # time interval. Simply reassign it the new calculated value.
                iv.value = dc  # a dual cost [$]

        # Ensure that only active time intervals are in the list of dual costs adc
        #self.dualCosts = [x for x in self.dualCosts if x.timeInterval in ti]

        # Sum the total dual cost and save the value
        self.totalDualCost = sum([x.value for x in self.dualCosts])

        dc = [(x.timeInterval.name, x.value) for x in self.dualCosts]
        _log.debug("{} asset model dual costs are: {}".format(self.name, dc))

    def update_production_costs(self, mkt):
        # Calculate the costs of generated energies.
        # (NOTE: Choosing not to separate this def from the base class because
        # cost might need to be handled differently and redefined in subclasses.)

        # Gather active time intervals ti
        time_intervals = mkt.timeIntervals
        time_interval_values = [t.startTime for t in time_intervals]
        self.productionCosts = [x for x in self.productionCosts if x.timeInterval.startTime in time_interval_values]

        # Index through the active time interval ti
        for i in range(1, len(time_intervals)):
            # Get the scheduled power sp in the indexed time interval
            sp = find_obj_by_ti(self.scheduledPowers, time_intervals[i])
            sp = sp.value  # schedule power [avg.kW]

            # Call on def that calculates production cost pc based on the
            # vertices of the supply or demand curve
            # NOTE that this def is now stand-alone because it might be
            # generally useful for a number of models.
            pc = prod_cost_from_vertices(self, time_intervals[i], sp)  # interval production cost [$]

            # Check for a transition cost in the indexed time interval.
            # (NOTE: this differs from neighbor models, which do not posses the
            # concept of commitment and engagement. This is a good reason to keep
            # this method within its base class to allow for subtle differences.)
            tc = find_obj_by_ti(self.transitionCosts, time_intervals[i])

            if tc is None:
                tc = 0.0  # [$]
            else:
                tc = tc.value  # [$]

            # Add the transition cost to the production cost
            pc = pc + tc

            # Check to see if the production cost value has been defined for the
            # indexed time interval
            iv = find_obj_by_ti(self.productionCosts, time_intervals[i])

            if iv is None:
                # The production cost value has not been defined in the indexed
                # time interval. Create it and assign its value pc.
                iv = IntervalValue(self, time_intervals[i], mkt, MeasurementType.ProductionCost, pc)

                # Append the production cost to the list of active production
                # cost values
                self.productionCosts.append(iv)  # IntervalValues

            else:
                # The production cost value already exists in the indexed time
                # interval. Simply reassign its value.
                iv.value = pc  # interval production cost [$]

        # Ensure that only active time intervals are in the list of active
        # production costs apc
        #self.productionCosts = [x for x in self.productionCosts if x.timeInterval in time_intervals]

        # Sum the total production cost
        self.totalProductionCost = sum([x.value for x in self.productionCosts])  # total production cost [$]

        pc = [(x.timeInterval.name, x.value) for x in self.productionCosts]
        _log.debug("{} asset model production costs are: {}".format(self.name, pc))

    def update_vertices(self, mkt):
        # Create vertices to represent the asset's flexibility
        #
        # For the base local asset model, a single, inelastic power is needed.
        # There is no flexibility. The constant power may be represented by a
        # single (price, power) point (See struct Vertex).

        # Gather active time intervals
        ti = mkt.timeIntervals  # active TimeIntervals
        time_interval_values = [t.startTime for t in ti]
        self.activeVertices = [x for x in self.activeVertices if x.timeInterval.startTime in time_interval_values]

        # Index through active time intervals ti
        for i in range(len(ti)):
            # Find the scheduled power for the indexed time interval
            # Extract the scheduled power value
            sp = find_obj_by_ti(self.scheduledPowers, ti[i])
            sp = sp.value  # avg. kW]

            # Create the vertex that can represent this (lack of) flexibility
            value = Vertex(float("inf"), 0.0, sp, True)

            # Check to see if the active vertex already exists for this indexed time interval.
            iv = find_obj_by_ti(self.activeVertices, ti[i])

            # If the active vertex does not exist, a new interval value must be
            # created and stored.
            if iv is None:
                # Create the interval value and place the active vertex in it
                iv = IntervalValue(self, ti[i], mkt, MeasurementType.ActiveVertex, value)

                # Append the interval value to the list of active vertices
                self.activeVertices.append(iv)

            else:
                # Otherwise, simply reassign the active vertex value to the
                # existing listed interval value. (NOTE that this base local
                # asset model unnecessarily reassigns constant values, but the
                # reassignment is allowed because it teaches how a more dynamic
                # assignment may be maintained.
                iv.value = value

        av = [(x.timeInterval.name, x.value.marginalPrice, x.value.power) for x in self.activeVertices]
        _log.debug("{} asset model active vertices are: {}".format(self.name, av))
