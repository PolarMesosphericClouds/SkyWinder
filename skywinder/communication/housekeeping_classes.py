import glob
import json
import logging
import os
import time
import math
import numpy as np

from skywinder.utils import file_reading

logger = logging.getLogger(__name__)

# These can go into constants file in the future.

SILENCE = 0
NOMINAL = 1
GOOD = 2
WARNING = 3
CRITICAL = 4
DELIMITER = ','


def construct_status_group_from_json(json_path, filewatcher_threshhold_time, override_preamble=None, name=None):
    # print '#### json path:', json_path
    # group_name = json_path.strip('.json')
    if name is None:
        group_name = os.path.splitext(os.path.split(json_path)[1])[0]
    else:
        group_name = name
    # print '#### group name:', group_name
    status_group = StatusGroup(group_name, filewatchers=[])

    with open(json_path, 'r') as f:
        json_dict = json.loads(f.read())
    json_range_path = os.path.splitext(json_path)[0] + '_ranges.json'
    with open(json_range_path, 'r') as f:
        range_result = json.loads(f.read())

    if override_preamble is None:
        preamble = json_dict['PREAMBLE']
    else:
        preamble = override_preamble
    items = json_dict["ITEMS"]

    missing_ranges = list(set(items.keys()).difference(set(range_result.keys())))
    if missing_ranges:
        logger.error("Missing ranges for the following keys: %r" % missing_ranges)

    for key in list(range_result.keys()):
        try:
            items[key].update(range_result[key])
        except KeyError as e:
            logger.error(' Could not find key %r in results from json.' % key)

    for value_key in list(items.keys()):
        if value_key == 'PREAMBLE':  # This is not a file to watch.
            continue
        value_dict = items[value_key]
        if value_dict['partial_glob'] not in status_group.filewatchers:
            try:
                status_filewatcher = StatusFileWatcher(name=value_dict['partial_glob'], items=[],
                                                       filename_glob=os.path.join(preamble, value_dict['partial_glob']),
                                                       threshhold_time=filewatcher_threshhold_time)
            except ValueError as e:
                logger.warning(
                    "Could not add StatusFileWatcher for glob %r\n%s" % (value_dict['partial_glob'], e.message))
                continue
            status_group.filewatchers[value_dict['partial_glob']] = status_filewatcher
        try:
            status_item = eval(value_dict['class_type'])(value_dict)
        except Exception as e:
            logger.exception('Problem while trying to create status_item. Value dict is: %r' % value_dict)
            continue

        status_group.filewatchers[value_dict['partial_glob']].items.update({status_item.name: status_item})

        status_group.filewatchers[value_dict['partial_glob']].items[status_item.name] = status_item

    return status_group


def construct_super_group_from_json_list(json_paths, filewatcher_threshhold_time):
    group_name = 'SuperGroup'
    super_group = SuperStatusGroup(group_name, groups=[])
    # print json_paths
    for i, json_path in enumerate(json_paths):
        try:
            status_group = construct_status_group_from_json(json_path, filewatcher_threshhold_time)
            super_group.groups[status_group.name] = status_group
        except ValueError as e:
            logger.exception("Error processing json_path %s" % (json_path))
    return super_group


class SuperStatusGroup():
    def __init__(self, name, groups):
        self.name = name
        self.groups = {}
        for group in groups:
            self.groups[group.name] = group
        self.three_column_data_set = self.get_three_column_data_set()

    def get_status_summary(self):
        status_summaries = [self.groups[key].get_status_summary() for key in list(self.groups.keys())]
        max_value = max([status_summary[0] for status_summary in status_summaries])
        name_list = []
        for status_summary in status_summaries:
            if status_summary[0] == max_value:
                name_list += status_summary[1]
        return (max_value, name_list)

    def update(self):
        logger.debug('Updating %r' % self.name)
        for key in list(self.groups.keys()):
            try:
                self.groups[key].update()
            except Exception as e:
                logger.exception('Error in updating %r' % key)
        self.three_column_data_set = self.get_three_column_data_set()

    def get_status(self):
        if len(self.groups) == 0:
            logger.error('No keys for %s - filewatcher is empty.' % self.name)
            return None
        entries = {key: self.groups[key].get_status() for key in list(self.groups.keys())}
        return entries

    def get_three_column_data_set(self):
        data_set = {}
        for group in list(self.groups.values()):
            for filewatcher in list(group.filewatchers.values()):
                for item in list(filewatcher.items.values()):
                    if item.name in list(data_set.keys()):
                        logger.error('Duplicate key %r found' % item.name)
                    data_set['%s.%s' % (group.name, item.name)] = (item.epoch, item.value)
        return data_set

    def get_value(self, item_name):
        try:
            return self.three_column_data_set[item_name][1]
        except KeyError as e:
            logger.warning('Key %r missing from group %r' % (item_name, self.name))
            return np.nan

    def get_recent_value(self, item_name, max_age_seconds=60):
        try:
            epoch, value = self.three_column_data_set[item_name]
        except KeyError as e:
            logger.warning('Key %r missing from group %r' % (item_name, self.name))
            return np.nan
        if epoch is None:
            logger.info("No entry for %r.%r (epoch is None)" % (self.name, item_name))
            return np.nan
        age = time.time() - epoch
        if age > max_age_seconds:
            logger.debug("Value %r for %r is too old, last updated %.1f seconds ago" % (value, item_name, age))
            return np.nan
        else:
            return value

    def get_epoch(self, item_name):
        try:
            return self.three_column_data_set[item_name][0]
        except KeyError as e:
            logger.error('Key %r missing from group %r' % (item_name, self.name))
            return np.nan


class StatusGroup():
    def __init__(self, name, filewatchers):
        self.name = name
        self.filewatchers = {}
        for filewatcher in filewatchers:
            self.filewatchers[filewatcher.name] = filewatcher

    def get_status_summary(self):
        status_summaries = [self.filewatchers[key].get_status_summary() for key in list(self.filewatchers.keys())]
        max_value = max([status_summary[0] for status_summary in status_summaries])
        name_list = []
        for status_summary in status_summaries:
            if status_summary[0] == max_value:
                name_list += status_summary[1]
        return (max_value, name_list)

    def update(self):
        logger.debug('Updating group with name %r' % self.name)
        for key in list(self.filewatchers.keys()):
            self.filewatchers[key].update()

    def get_status(self):
        if len(self.filewatchers) == 0:
            logger.error('No keys for %s - filewatcher is empty.' % self.name)
            return None
        entries = {key: self.filewatchers[key].get_status() for key in list(self.filewatchers.keys())}
        return entries


class StatusFileWatcher():
    def __init__(self, name, items, filename_glob, threshhold_time):
        # example, charge_controller.csv, charge_controller

        self.glob = filename_glob
        self.threshhold_time = threshhold_time

        self.assign_file(self.glob)

        self.last_update = None
        self.name = name

        self.column_names = None
        self.items = {}
        for item in items:
            print(item)
            self.items[item.name] = item

    def assign_file(self, filename_glob):
        files = glob.glob(filename_glob)
        if len(files) == 0:
            raise ValueError('No files found with filename_glob %r' % filename_glob)
        files.sort()
        self.source_file = files[-1]
        logger.debug('File %r set' % self.source_file)

    def get_status_summary(self):
        if len(list(self.items.keys())) == 0:
            raise ValueError('No keys - filewatcher is empty.')
        values = [self.items[key].get_status_summary() for key in list(self.items.keys())]
        max_value = max(values)
        max_indices = [i for i, value in enumerate(values) if (value == max_value)]
        return (max_value, [list(self.items.keys())[i] for i in max_indices])

    def get_status(self):
        if len(list(self.items.keys())) == 0:
            raise ValueError('No keys - filewatcher is empty.')
        entries = (self.items[key].get_status() for key in list(self.items.keys()))
        return dict(list(zip(list(self.items.keys()), entries)))

    def update(self):
        if self.column_names is None:
            logger.debug('Getting column names for %r' % self.name)
            with open(self.source_file, 'r') as f:
                f.seek(0, 0)
                name_line = f.readline()
                while name_line.startswith('#'):
                    # Ignore headers
                    name_line = f.readline()
                self.column_names = (name_line.strip()).split(DELIMITER)
                if self.column_names[0] != 'epoch':
                    raise ValueError(
                        'First column of file %r is not epoch, it is %r' % (self.source_file, self.column_names[0]))

        last_update = os.path.getmtime(self.source_file)

        if time.time() - last_update > self.threshhold_time:  # check if the last update of the file is within some threshhold.
            self.assign_file(self.glob)  # Get the newest file with the given glob (this glob should not change)
            last_update = os.path.getmtime(self.source_file)  # Find the last_update for the updated newest file.

        if last_update == self.last_update:  # if the file not has changed since last check
            # logger.debug('File %r up to date.' % self.name)
            return

        else:
            last_line = file_reading.read_last_line(self.source_file)
            values = last_line.split(DELIMITER)
            if values[0] == 'epoch':
                return  # there is no data in the file yet
            self.last_update = last_update
            # logger.debug('Filewatcher %r updated with values %r' % (self.name, values))

        if len(values) != len(self.column_names):
            raise ValueError(
                'For filewatcher %r: Number of values and column names mismatch. %d Values, %d column names' %
                (self.name, len(values), len(self.column_names)))
        value_dict = dict(list(zip(self.column_names, values)))

        for key in list(self.items.keys()):
            self.items[key].update_value(value_dict)


class FloatStatusItem():
    def __init__(self, value_dict):
        # Example solar cell voltage
        self.name = value_dict['name']
        self.column_name = value_dict['column_name']
        self.value = None
        self.epoch = None
        self.normal_range = Range(float(value_dict['normal_range_low']), float(value_dict['normal_range_high']))
        self.good_range = Range(float(value_dict['good_range_low']), float(value_dict['good_range_high']))
        self.warning_range = Range(float(value_dict['warning_range_low']), float(value_dict['warning_range_high']))
        self.silenced = False
        self.scaling = float(value_dict['scaling'])

    # Add silence, epoch

    def update_value(self, value_dict):
        if self.column_name in value_dict:
            self.unscaled_value = float(value_dict[self.column_name])
            self.value = self.unscaled_value * self.scaling
        else:
            logger.warning('Column name %r for item %r not found in columns: %r' %
                           (self.column_name, self.name, list(value_dict.keys())))
        self.epoch = float(value_dict['epoch'])

    def get_status_summary(self):
        if self.silenced:
            return SILENCE
        if self.normal_range:
            if self.value in self.normal_range:
                return NOMINAL
        if self.good_range:
            if self.value in self.good_range:
                return GOOD
        if self.warning_range:
            if self.value in self.warning_range:
                return WARNING
        return CRITICAL

    def get_status(self):
        # TODO: Add unscaled value and scaling if scaling != 1
        return dict(column_name=self.column_name, value=self.value, epoch=self.epoch)


class StringStatusItem():
    def __init__(self, value_dict):
        # Example solar cell voltage
        self.name = value_dict['name']
        self.column_name = value_dict['column_name']
        self.value = None
        self.epoch = None
        self.normal_string = value_dict['normal_string']
        self.good_string = value_dict['good_string']
        self.warning_string = value_dict.get('warning_string', '')
        self.silenced = False

    # Add silence, epoch

    def update_value(self, value_dict):
        if self.column_name in value_dict:
            self.value = str(value_dict[self.column_name])
            self.epoch = float(value_dict['epoch'])
            # logger.debug('Item %r updated with value %r' % (self.name, self.value)) # Too much logging.

    def get_status_summary(self):
        if self.silenced:
            return SILENCE

        if self.normal_string:
            if isinstance(self.normal_string, list):
                if self.value in self.normal_string:
                    return NOMINAL
            else:
                if self.value == self.normal_string:
                    return NOMINAL

        if self.good_string:
            if isinstance(self.good_string, list):
                if self.value in self.good_string:
                    return GOOD
            else:
                if self.value == self.good_string:
                    return GOOD

        if self.warning_string:
            if isinstance(self.warning_string, list):
                if self.value in self.warning_string:
                    return WARNING
            else:
                if self.value == self.warning_string:
                    return WARNING

        return CRITICAL

    def get_status(self):
        return dict(column_name=self.column_name, value=self.value, epoch=self.epoch)


class Range():
    def __init__(self, min, max):

        if not (isinstance(min, int) or isinstance(min, float)):
            raise TypeError("Min %r is not an int or float. It is a %r" % (min, type(min)))

        if not (isinstance(max, int) or isinstance(max, float)):
            raise TypeError("Max %r is not an int or float. It is a %r " % (max, type(max)))

        if min == float('nan') and max != float('nan'):
            raise ValueError('Either both min or max are float or neither are. Only min is float.')

        if max == float('nan') and min != float('nan'):
            raise ValueError('Either both min or max are float or neither are. Only max is float.')

        self.ranges = [(min, max)]

    def __contains__(self, item):
        for range_ in self.ranges:
            if math.isnan(range_[0]) or math.isnan(range_[1]):
                return True

            if range_[0] <= item <= range_[1]:
                return True

            else:
                return False

        return False

    def __add__(self, other):
        self.ranges += other.ranges
