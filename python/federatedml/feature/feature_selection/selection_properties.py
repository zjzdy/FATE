#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
#  Copyright 2019 The FATE Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.


import operator

from federatedml.protobuf.generated import feature_selection_param_pb2
from federatedml.util import LOGGER


class SelectionProperties(object):
    def __init__(self):
        self.header = []
        self.anonymous_header = []
        self.anonymous_col_name_maps = {}
        self.col_name_maps = {}
        self.last_left_col_indexes = []
        self.select_col_indexes = []
        self.select_col_names = []
        # self.anonymous_select_col_names = []
        self.left_col_indexes_added = set()
        self.left_col_indexes = []
        self.left_col_names = []
        # self.anonymous_left_col_names = []
        self.feature_values = {}

    def load_properties_with_new_header(self, header, feature_values, left_cols_obj, new_header_dict):
        self.set_header(list(new_header_dict.values()))
        self.set_last_left_col_indexes([header.index(i) for i in left_cols_obj.original_cols])
        self.add_select_col_names([new_header_dict.get(col) for col in left_cols_obj.original_cols])
        for col_name, _ in feature_values.items():
            self.add_feature_value(new_header_dict.get(col_name), feature_values.get(col_name))
        left_cols_dict = dict(left_cols_obj.left_cols)
        # LOGGER.info(f"left_cols_dict: {left_cols_dict}")
        for col_name, _ in left_cols_dict.items():
            if left_cols_dict.get(col_name):
                self.add_left_col_name(new_header_dict.get(col_name))
                # LOGGER.info(f"select properties all left cols names: {self.all_left_col_names}")

        return self

    def load_properties(self, header, feature_values, left_cols_obj):
        self.set_header(header)
        self.set_last_left_col_indexes([header.index(i) for i in left_cols_obj.original_cols])
        self.add_select_col_names(left_cols_obj.original_cols)
        for col_name, _ in feature_values.items():
            self.add_feature_value(col_name, feature_values[col_name])
        left_cols_dict = dict(left_cols_obj.left_cols)
        for col_name, _ in left_cols_dict.items():
            if left_cols_dict[col_name]:
                self.add_left_col_name(col_name)
        return self

    def set_header(self, header):
        self.header = header
        for idx, col_name in enumerate(self.header):
            self.col_name_maps[col_name] = idx

    def set_anonymous_header(self, anonymous_header):
        self.anonymous_header = anonymous_header
        if self.anonymous_header:
            for idx, col_name in enumerate(self.anonymous_header):
                self.anonymous_col_name_maps[col_name] = idx

    def set_last_left_col_indexes(self, left_cols):
        self.last_left_col_indexes = left_cols.copy()

    def set_select_all_cols(self):
        self.select_col_indexes = [i for i in range(len(self.header))]
        self.select_col_names = self.header
        # self.anonymous_select_col_names = self.anonymous_header

    def add_select_col_indexes(self, select_col_indexes):
        last_left_col_indexes = set(self.last_left_col_indexes)
        added_select_col_index = set(self.select_col_indexes)
        for idx in select_col_indexes:
            if idx >= len(self.header):
                LOGGER.warning("Adding an index out of header's bound")
                continue
            if idx not in last_left_col_indexes:
                continue

            if idx not in added_select_col_index:
                self.select_col_indexes.append(idx)
                self.select_col_names.append(self.header[idx])
                # self.anonymous_select_col_names.append(self.anonymous_header[idx])
                added_select_col_index.add(idx)

    def add_select_col_names(self, select_col_names):
        last_left_col_indexes = set(self.last_left_col_indexes)
        added_select_col_indexes = set(self.select_col_indexes)

        for col_name in select_col_names:
            idx = self.col_name_maps.get(col_name)
            if idx is None:
                LOGGER.warning("Adding a col_name that does not exist in header")
                continue
            if idx not in last_left_col_indexes:
                continue
            if idx not in added_select_col_indexes:
                self.select_col_indexes.append(idx)
                self.select_col_names.append(col_name)
                # self.anonymous_select_col_names.append(self.anonymous_header[idx])
                added_select_col_indexes.add(idx)

    def add_left_col_name(self, left_col_name):
        idx = self.col_name_maps.get(left_col_name)
        if idx is None:
            LOGGER.warning("Adding a col_name that does not exist in header")
            return
        if idx not in self.left_col_indexes_added:
            self.left_col_indexes.append(idx)
            self.left_col_indexes_added.add(idx)
            self.left_col_names.append(left_col_name)
            # self.anonymous_left_col_names.append(self.anonymous_header[idx])

    def add_feature_value(self, col_name, feature_value):
        self.feature_values[col_name] = feature_value

    @property
    def all_left_col_indexes(self):
        result = []
        select_col_indexes = set(self.select_col_indexes)
        left_col_indexes = set(self.left_col_indexes)
        for idx in self.last_left_col_indexes:
            if (idx not in select_col_indexes) or (idx in left_col_indexes):
                result.append(idx)
            # elif idx in left_col_indexes:
            #    result.append(idx)
        return result

    @property
    def all_left_col_names(self):
        return [self.header[x] for x in self.all_left_col_indexes]

    @property
    def all_left_anonymous_col_names(self):
        return [self.anonymous_header[x] for x in self.all_left_col_indexes]

    @property
    def left_col_dicts(self):
        return {x: True for x in self.all_left_col_names}

    @property
    def last_left_col_names(self):
        return [self.header[x] for x in self.last_left_col_indexes]


class CompletedSelectionResults(object):
    def __init__(self):
        self.header = []
        self.anonymous_header = []
        self.col_name_maps = {}
        self.__select_col_names = None
        self.filter_results = []
        self.__guest_pass_filter_nums = {}
        self.__host_pass_filter_nums_list = []
        self.all_left_col_indexes = []

    def set_header(self, header):
        self.header = header
        for idx, col_name in enumerate(self.header):
            self.col_name_maps[col_name] = idx

    def set_anonymous_header(self, anonymous_header):
        self.anonymous_header = anonymous_header

    def set_select_col_names(self, select_col_names):
        if self.__select_col_names is None:
            self.__select_col_names = select_col_names

    def get_select_col_names(self):
        return self.__select_col_names

    def set_all_left_col_indexes(self, left_indexes):
        self.all_left_col_indexes = left_indexes.copy()

    @property
    def all_left_col_names(self):
        return [self.header[x] for x in self.all_left_col_indexes]

    @property
    def all_left_anonymous_col_names(self):
        return [self.anonymous_header[x] for x in self.all_left_col_indexes]

    def add_filter_results(self, filter_name, select_properties: SelectionProperties, host_select_properties=None):
        # self.all_left_col_indexes = select_properties.all_left_col_indexes.copy()
        self.set_all_left_col_indexes(select_properties.all_left_col_indexes)
        if filter_name == 'conclusion':
            return

        if host_select_properties is None:
            host_select_properties = []

        host_feature_values = []
        host_left_cols = []
        for idx, host_result in enumerate(host_select_properties):
            host_all_left_col_names = set(host_result.all_left_col_names)
            if idx >= len(self.__host_pass_filter_nums_list):
                _host_pass_filter_nums = {}
                self.__host_pass_filter_nums_list.append(_host_pass_filter_nums)
            else:
                _host_pass_filter_nums = self.__host_pass_filter_nums_list[idx]
            host_last_left_col_names = host_result.last_left_col_names
            for col_name in host_last_left_col_names:
                _host_pass_filter_nums.setdefault(col_name, 0)
                if col_name in host_all_left_col_names:
                    _host_pass_filter_nums[col_name] += 1

            feature_value_pb = feature_selection_param_pb2.FeatureValue(feature_values=host_result.feature_values)
            host_feature_values.append(feature_value_pb)
            left_col_pb = feature_selection_param_pb2.LeftCols(original_cols=host_last_left_col_names,
                                                               left_cols=host_result.left_col_dicts)
            host_left_cols.append(left_col_pb)

        # for col_name in select_properties.all_left_col_names:
        self_all_left_col_names = set(select_properties.all_left_col_names)
        self_last_left_col_names = select_properties.last_left_col_names
        for col_name in self_last_left_col_names:
            self.__guest_pass_filter_nums.setdefault(col_name, 0)
            if col_name in self_all_left_col_names:
                self.__guest_pass_filter_nums[col_name] += 1

        left_cols_pb = feature_selection_param_pb2.LeftCols(original_cols=self_last_left_col_names,
                                                            left_cols=select_properties.left_col_dicts)

        this_filter_result = {
            'feature_values': select_properties.feature_values,
            'host_feature_values': host_feature_values,
            'left_cols': left_cols_pb,
            'host_left_cols': host_left_cols,
            'filter_name': filter_name
        }
        this_filter_result = feature_selection_param_pb2.FeatureSelectionFilterParam(**this_filter_result)
        self.filter_results.append(this_filter_result)

    def get_sorted_col_names(self):
        result = sorted(self.__guest_pass_filter_nums.items(), key=operator.itemgetter(1), reverse=True)
        return [x for x, _ in result]

    def get_host_sorted_col_names(self):
        result = []
        for pass_name_dict in self.__host_pass_filter_nums_list:
            sorted_list = sorted(pass_name_dict.items(), key=operator.itemgetter(1), reverse=True)
            result.append([x for x, _ in sorted_list])
        return result
