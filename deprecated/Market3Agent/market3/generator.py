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

import os
import sys
import logging
from datetime import datetime
from dateutil import parser
import numpy as np


class Generator:
    def __init__(self):
        # TODO: Add to config file later...
        self.c1 = [3.243, 30]  # generation cost
        self.r1 = [2, 10]  # reserve cost
        self.plower1 = 0.3  # lower bound of power production
        self.pupper1 = 100  # upper bound of power production
        self.ramp = 0.5  # ramp rate constraint

    def generate_bid(self, T, price_energy, price_reserved):
        lam = price_energy
        rp = price_reserved

        power_supply, reserve_desired = self.generate(T, lam, self.c1,
                                                      self.plower1, self.pupper1,
                                                      self.ramp, self.r1, rp)

        return power_supply, reserve_desired

    def generate(self, T, lam, c, plower, pupper, ramp, rc, rp):
        import cvxpy as cp

        constraints = []
        u = cp.Variable((T, 1))
        r = cp.Variable((T, 1))
        objective = cp.Minimize(cp.sum(
            c[0] * u ** 2 + cp.multiply(c[1], u) + rc[0] * r ** 2 + rc[1] * r - cp.multiply(lam, u) - cp.multiply(rp,
                                                                                                                  r)))
        for i in range(0, T):
            constraints += [
                u[i] >= plower,
                u[i] <= pupper,
                r[i] >= 0
            ]
            if i < T - 1:
                constraints += [
                    u[i + 1] - u[i] <= ramp,
                    u[i] - u[i + 1] <= ramp]
        prob = cp.Problem(objective, constraints)
        result = prob.solve(solver=cp.ECOS_BB, verbose=True)

        return u.value, r.value


if __name__ == '__main__':
    generator = Generator()

    T = 24
    lam = 40 * np.full((T, 1), 1)
    rp = 15 * np.full((T, 1), 1)
    c = [3.243, 30]
    rc = [2, 10]
    plower = 0.3
    pupper = 100
    ramp = 0.5
    u, v = generator.generate(T, lam, c, plower, pupper, ramp, rc, rp)

    print(u)
    print(v)

