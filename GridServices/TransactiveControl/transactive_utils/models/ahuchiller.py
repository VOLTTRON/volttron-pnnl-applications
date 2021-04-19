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
import importlib

from volttron.platform.agent import utils
import transactive_utils.models.input_names as data_names

_log = logging.getLogger(__name__)
utils.setup_logging()

class ahuchiller(object):

    def __init__(self, config, parent, **kwargs):
        self.parent = parent
        equipment_conf = config.get("equipment_configuration")
        model_conf = config.get("model_configuration")
        self.cpAir = model_conf["cpAir"]
        self.c0 = float(model_conf["c0"])
        self.c1 = float(model_conf["c1"])
        self.c2 = float(model_conf["c2"])
        self.c3 = float(model_conf["c3"])
        self.power_unit = model_conf.get("unit_power", "kw")
        self.cop = model_conf["COP"]
        self.mDotAir = model_conf.get("mDotAir", 0.0)

        self.name = 'AhuChiller'

        self.has_economizer = equipment_conf["has_economizer"]
        if self.has_economizer:
            self.economizer_limit = equipment_conf["economizer_limit"]
        else:
            self.economizer_limit = 0
        self.min_oaf = equipment_conf.get("minimum_oaf", 0.15)
        self.vav_flag = equipment_conf.get("variable_volume", True)
        self.sat_setpoint = equipment_conf["supply_air_setpoint"]
        self.building_chiller = equipment_conf["building_chiller"]
        self.tset_avg = equipment_conf["nominal_zone_setpoint"]
        self.tDis = self.sat_setpoint
        self.parent.supply_commodity = "ZoneAirFlow"

        self.fan_power = 0.
        self.coil_load = 0.

        self.get_input_value = parent.get_input_value
        self.smc_interval = parent.single_market_contol_interval
        self.parent = parent
        self.sfs_name = data_names.SFS
        self.mat_name = data_names.MAT
        self.dat_name = data_names.DAT
        self.saf_name = data_names.SAF
        self.oat_name = data_names.OAT
        self.rat_name = data_names.RAT

        self.sfs = None
        self.mat = None
        self.dat = None
        self.saf = None
        self.oat = None
        self.rat = None

    def update_data(self):
        self.sfs = self.get_input_value(self.sfs_name)
        self.mat = self.get_input_value(self.mat_name)
        self.dat = self.get_input_value(self.dat_name)
        self.saf = self.get_input_value(self.saf_name)
        self.oat = self.get_input_value(self.oat_name)
        self.rat = self.get_input_value(self.rat_name)

    def input_zone_load(self, q_load):
        if self.vav_flag:
            self.mDotAir = q_load
        else:
            self.tDis = q_load
            self.dat = q_load
            self.mDotAir = self.saf

    def calculate_fan_power(self):
        if self.power_unit == 'W':
            self.fan_power = (self.c0 + self.c1*self.mDotAir + self.c2*pow(self.mDotAir, 2) + self.c3*pow(self.mDotAir, 3))*1000.  # watts
        else:
            self.fan_power = self.c0 + self.c1*self.mDotAir + self.c2*pow(self.mDotAir, 2) + self.c3*pow(self.mDotAir, 3)  # kW

    def calculate_coil_load(self, oat):
        if self.has_economizer:
            if oat < self.tDis:
                coil_load = 0.0
            elif oat < self.economizer_limit:
                coil_load = self.mDotAir * self.cpAir * (self.tDis - oat)
            else:
                mat = self.tset_avg*(1.0 - self.min_oaf) + self.min_oaf*oat
                coil_load = self.mDotAir * self.cpAir * (self.tDis - mat)
        else:
            mat = self.tset_avg * (1.0 - self.min_oaf) + self.min_oaf * oat
            coil_load = self.mDotAir * self.cpAir * (self.tDis - mat)

        if coil_load > 0: #heating mode is not yet supported!
            self.coil_load = 0.0
        else:
            self.coil_load = coil_load

    def calculate_load(self, q_load, oat):
        self.input_zone_load(q_load)
        return self.calculate_total_power(oat)

    def single_market_coil_load(self):
        try:
            self.coil_load = self.mDotAir * self.cpAir * (self.dat - self.mat)
            _log.debug("AHU MODEL - load: %s -- mdot: %s -- mat: %s -- dat: %s", self.coil_load, self.mDotAir, self.mat, self.dat)
        except:
            _log.debug("AHU for single market requires dat and mat measurements!")
            self.coil_load = 0.

    def calculate_total_power(self, oat):
        self.calculate_fan_power()
        oat = oat if oat is not None else self.oat
        if self.building_chiller and oat is not None:
            if self.smc_interval is not None:
                self.single_market_coil_load()
            else:
                self.calculate_coil_load(oat)
        else:
            _log.debug("AHUChiller building does not have chiller or no oat!")
            self.coil_load = 0.0
        return abs(self.coil_load)/self.cop/0.9 + max(self.fan_power, 0)
