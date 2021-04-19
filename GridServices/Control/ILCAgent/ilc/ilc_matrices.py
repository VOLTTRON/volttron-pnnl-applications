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

import operator
import logging
import math
from volttron.platform.agent import utils
from collections import defaultdict
from functools import reduce

utils.setup_logging()
_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.debug,
                    format='%(asctime)s   %(levelname)-8s %(message)s',
                    datefmt='%m-%d-%y %H:%M:%S')


def extract_criteria(filename):
    """
    Extract pairwise criteria parameters
    :param filename:
    :return:
    """
    criteria_labels = {}
    criteria_matrix = {}
    # config_matrix = utils.load_config(filename)
    config_matrix = filename
    # check if file has been updated or uses old format
    _log.debug("CONFIG_MATRIX: {}".format(config_matrix))
    if "curtail" not in config_matrix.keys() and "augment" not in config_matrix.keys():
        config_matrix = {"curtail": config_matrix}

    _log.debug("CONFIG_MATRIX: {}".format(config_matrix))
    for state in config_matrix:
        index_of = dict([(a, i) for i, a in enumerate(config_matrix[state].keys())])

        criteria_labels[state] = []
        for label, index in index_of.items():
            criteria_labels[state].insert(index, label)

        criteria_matrix[state] = [[0.0 for _ in config_matrix[state]] for _ in config_matrix[state]]
        for j in config_matrix[state]:
            row = index_of[j]
            criteria_matrix[state][row][row] = 1.0

            for k in config_matrix[state][j]:
                col = index_of[k]
                criteria_matrix[state][row][col] = float(config_matrix[state][j][k])
                criteria_matrix[state][col][row] = float(1.0 / criteria_matrix[state][row][col])

    return criteria_labels, criteria_matrix, list(config_matrix.keys())


def calc_column_sums(criteria_matrix):
    """
    Calculate the column sums for the criteria matrix.
    :param criteria_matrix:
    :return:
    """
    cumsum = {}
    for state in criteria_matrix:
        j = 0
        cumsum[state] = []
        while j < len(criteria_matrix[state][0]):
            col = [float(row[j]) for row in criteria_matrix[state]]
            cumsum[state].append(sum(col))
            j += 1
    return cumsum


def normalize_matrix(criteria_matrix, col_sums):
    """
    Normalizes the members of criteria matrix using the vector
    col_sums. Returns sums of each row of the matrix.
    :param criteria_matrix:
    :param col_sums:
    :return:
    """
    normalized_matrix = {}
    row_sums = {}
    for state in criteria_matrix:
        normalized_matrix[state] = []
        row_sums[state] = []
        i = 0
        while i < len(criteria_matrix[state]):
            j = 0
            norm_row = []
            while j < len(criteria_matrix[state][0]):
                norm_row.append(criteria_matrix[state][i][j]/(col_sums[state][j] if col_sums[state][j] != 0 else 1))
                j += 1
            row_sum = sum(norm_row)
            norm_row.append(row_sum/j)
            row_sums[state].append(row_sum/j)
            normalized_matrix[state].append(norm_row)
            i += 1
    return row_sums


def validate_input(pairwise_matrix, col_sums):
    """
    Validates the criteria matrix to ensure that the inputs are

    internally consistent. Returns a True if the matrix is valid,
    and False if it is not.
    :param pairwise_matrix:
    :param col_sums:
    :return:
    """
    # Calculate row products and take the 5th root
    _log.info("Validating matrix")
    consistent = True
    for state in pairwise_matrix:
        random_index = [0, 0, 0, 0.58, 0.9, 1.12, 1.24, 1.32, 1.41, 1.45, 1.49]
        roots = []
        for row in pairwise_matrix[state]:
            roots.append(math.pow(reduce(operator.mul, row, 1), 1.0/5))
        # Sum the vector of products
        root_sum = sum(roots)
        # Calculate the priority vector
        priority_vec = []
        for item in roots:
            priority_vec.append(item / root_sum)

        # Calculate the priority row
        priority_row = []
        for i in range(0, len(col_sums[state])):
            priority_row.append(col_sums[state][i] * priority_vec[i])

        # Sum the priority row
        priority_row_sum = sum(priority_row)

        # Calculate the consistency index
        ncols = max(len(col_sums[state]) - 1, 1)
        consistency_index = \
            (priority_row_sum - len(col_sums[state]))/ncols

        # Calculate the consistency ratio
        if len(col_sums[state]) < 4:
            consistency_ratio = consistency_index
        else:
            rindex = random_index[len(col_sums[state])]
            consistency_ratio = consistency_index / rindex

        _log.debug("Pairwise comparison: {} - CR: {}".format(state, consistency_index))
        if consistency_ratio > 0.2:
            consistent = False
            _log.debug("Inconsistent pairwise comparison: {} - CR: {}".format(state, consistency_ratio))

    return consistent


def build_score(_matrix, weight, priority):
    """
    Calculates the curtailment score using the normalized matrix
    and the weights vector. Returns a sorted vector of weights for each
    device that is a candidate for curtailment.
    :param _matrix:
    :param weight:
    :param priority:
    :return:
    """
    input_keys, input_values = _matrix.keys(), _matrix.values()
    scores = []

    for input_array in input_values:
        criteria_sum = sum(i*w for i, w in zip(input_array, weight))

        scores.append(criteria_sum*priority)

    return zip(scores, input_keys)


def input_matrix(builder, criteria_labels):
    """
    Construct input normalized input matrix.
    :param builder:
    :param criteria_labels:
    :return:
    """
    sum_mat = defaultdict(float)
    inp_mat = {}
    label_check = list(list(builder.values())[-1].keys())
    if set(label_check) != set(criteria_labels):
        raise Exception('Input criteria and data criteria do not match.')
    for device_data in builder.values():
        for k, v in device_data.items():
            sum_mat[k] += v
    for key in builder:
        inp_mat[key] = mat_list = []
        for tag in criteria_labels:
            builder_value = builder[key][tag]
            if builder_value:
                mat_list.append(builder_value/sum_mat[tag])
            else:
                mat_list.append(0.0)

    return inp_mat
