import tempfile
import unittest
import numpy as np

from skywinder.communication import housekeeping_classes
import time


class StatusDictTest(unittest.TestCase):
    def test_item(self):
        item_value_dict = dict(name='test_item', column_name='value',
                               normal_range_low=0, normal_range_high=1,
                               good_range_low=1, good_range_high=2,
                               warning_range_low=2, warning_range_high=3, scaling=1)

        item = housekeeping_classes.FloatStatusItem(item_value_dict)
        value_dict = {'epoch': 1000, 'value': 0.5}
        item.update_value(value_dict)
        assert (item.get_status_summary() == housekeeping_classes.NOMINAL)
        value_dict = {'epoch': 1000, 'value': 1.5}
        item.update_value(value_dict)
        assert (item.get_status_summary() == housekeeping_classes.GOOD)
        value_dict = {'epoch': 1000, 'value': 2.5}
        item.update_value(value_dict)
        assert (item.get_status_summary() == housekeeping_classes.WARNING)

    def test_filewatcher(self):
        tfile = tempfile.NamedTemporaryFile()

        with open(tfile.name, 'w') as f:
            f.write('epoch,data0,data1\n')
            f.write('1000,1,5\n')

        value_dict_0 = dict(name='data0', column_name='data0',
                            normal_range_low=0, normal_range_high=1,
                            good_range_low=1, good_range_high=2,
                            warning_range_low=2, warning_range_high=3, scaling=1)

        item0 = housekeeping_classes.FloatStatusItem(value_dict_0)

        value_dict_1 = dict(name='data1', column_name='data1',
                            normal_range_low=0, normal_range_high=1,
                            good_range_low=1, good_range_high=2,
                            warning_range_low=2, warning_range_high=3, scaling=1)
        item1 = housekeeping_classes.FloatStatusItem(value_dict_1)
        items = [item0, item1]
        filewatcher = housekeeping_classes.StatusFileWatcher(name='test_filewatcher', items=items,
                                                             filename_glob=tfile.name, threshhold_time=60)
        filewatcher.update()

        print(item0.value)

        print(filewatcher.get_status_summary())
        assert (item0.value == 1)
        assert (item1.value == 5)
        assert (filewatcher.get_status_summary() == (housekeeping_classes.CRITICAL, ['data1']))

    def test_status_group(self):
        tfile0 = tempfile.NamedTemporaryFile()
        tfile1 = tempfile.NamedTemporaryFile()

        with open(tfile0.name, 'w') as f:
            f.write('epoch,data0,data1\n')
            f.write('1000,1,5\n')

        with open(tfile1.name, 'w') as f:
            f.write('epoch,data2,data3\n')
            f.write('1000,5,5\n')

        value_dict_0 = dict(name='data0', column_name='data0',
                            normal_range_low=0, normal_range_high=1,
                            good_range_low=1, good_range_high=2,
                            warning_range_low=2, warning_range_high=3, scaling=1)
        item0 = housekeeping_classes.FloatStatusItem(value_dict_0)

        value_dict_1 = dict(name='data1', column_name='data1',
                            normal_range_low=0, normal_range_high=1,
                            good_range_low=1, good_range_high=2,
                            warning_range_low=2, warning_range_high=3, scaling=1)
        item1 = housekeeping_classes.FloatStatusItem(value_dict_1)
        items0 = [item0, item1]
        filewatcher0 = housekeeping_classes.StatusFileWatcher(name='test_filewatcher0', items=items0,
                                                              filename_glob=tfile0.name, threshhold_time=60)

        value_dict_2 = dict(name='data2', column_name='data2', normal_string='-',good_string='-', warning_string='-')
        item2 = housekeeping_classes.StringStatusItem(value_dict_2)
        value_dict_3 = dict(name='data3', column_name='data3', normal_string='-',good_string='-', warning_string='-')
        item3 = housekeeping_classes.StringStatusItem(value_dict_3)
        items1 = [item2, item3]
        filewatcher1 = housekeeping_classes.StatusFileWatcher(name='test_filewatcher1', items=items1,
                                                              filename_glob=tfile1.name, threshhold_time=60)

        status_group = housekeeping_classes.StatusGroup('test_group', [filewatcher0, filewatcher1])
        status_group.update()

        status_summary = status_group.get_status_summary()

        assert (status_summary[0] == housekeeping_classes.CRITICAL)
        assert (set(status_summary[1]) == set(['data1', 'data3', 'data2']))
        full_status = status_group.get_status()
        assert ('test_filewatcher0' in list(full_status.keys()))
        assert ('test_filewatcher1' in list(full_status.keys()))

    def test_status_group_no_filewatchers(self):
        status_group = housekeeping_classes.StatusGroup('test_group', [])
        assert (status_group.get_status() == None)

    def test_super_status_group(self):
        tfile0 = tempfile.NamedTemporaryFile()
        tfile1 = tempfile.NamedTemporaryFile()

        with open(tfile0.name, 'w') as f:
            f.write('epoch,data0,data1\n')
            f.write('1000,1,5\n')

        with open(tfile1.name, 'w') as f:
            f.write('epoch,data2,data3\n')
            f.write('1000,5,5\n')

        value_dict_0 = dict(name='data0', column_name='data0',
                            normal_range_low=0, normal_range_high=1,
                            good_range_low=1, good_range_high=2,
                            warning_range_low=2, warning_range_high=3, scaling=1)
        item0 = housekeeping_classes.FloatStatusItem(value_dict_0)

        value_dict_1 = dict(name='data1', column_name='data1',
                            normal_range_low=0, normal_range_high=1,
                            good_range_low=1, good_range_high=2,
                            warning_range_low=2, warning_range_high=3, scaling=1)
        item1 = housekeeping_classes.FloatStatusItem(value_dict_1)
        items0 = [item0, item1]
        filewatcher0 = housekeeping_classes.StatusFileWatcher(name='test_filewatcher0', items=items0,
                                                              filename_glob=tfile0.name, threshhold_time=60)

        value_dict_2 = dict(name='data2', column_name='data2',
                            normal_range_low=0, normal_range_high=1,
                            good_range_low=1, good_range_high=2,
                            warning_range_low=2, warning_range_high=3, scaling=1)
        item2 = housekeeping_classes.FloatStatusItem(value_dict_2)
        value_dict_3 = dict(name='data3', column_name='data3',
                            normal_range_low=0, normal_range_high=1,
                            good_range_low=1, good_range_high=2,
                            warning_range_low=2, warning_range_high=3, scaling=1)
        item3 = housekeeping_classes.FloatStatusItem(value_dict_3)
        items1 = [item2, item3]
        filewatcher1 = housekeeping_classes.StatusFileWatcher(name='test_filewatcher1', items=items1,
                                                              filename_glob=tfile1.name, threshhold_time=60)

        status_group_0 = housekeeping_classes.StatusGroup('test_group', [filewatcher0, filewatcher1])
        status_group_1 = housekeeping_classes.StatusGroup('test_group', [filewatcher0, filewatcher1])
        status_group_0.update()
        status_group_1.update()

        super_status_group = housekeeping_classes.SuperStatusGroup('test_super_group', [status_group_0, status_group_1])

        assert (super_status_group.get_status_summary() != None)
        assert (super_status_group.get_status() != None)
        assert (super_status_group.get_three_column_data_set() != None)


class FilewatcherFileUpdateTest(unittest.TestCase):
    def test_file_flip(self):
        value_dict = {'name': 'test_item', 'column_name': 'value',
                      'normal_range_high': np.nan, 'normal_range_low': np.nan,
                      'good_range_high': np.nan, 'good_range_low': np.nan,
                      'warning_range_high': np.nan, 'warning_range_low': np.nan,
                      'scaling': 1.0}
        test_item = housekeeping_classes.FloatStatusItem(value_dict)

        first_file = tempfile.NamedTemporaryFile()
        with open(first_file.name, 'w') as f:
            f.write('epoch,value\n'
                    '1,2\n')

        filewatcher = housekeeping_classes.StatusFileWatcher('test_filewatcher', [test_item],
                                                             first_file.name, threshhold_time=1)
        filewatcher.update()
        print(filewatcher.items)
        time.sleep(2)
        second_file = tempfile.NamedTemporaryFile()
        with open(second_file.name, 'w') as f:
            f.write('#uselessheader1\n'
                    '#uselessheader2\n'
                    'epoch,value\n'
                    '3,4\n')
        filewatcher.glob = second_file.name
        filewatcher.update()
        print(filewatcher.items)
        assert (filewatcher.items['test_item'].value == 4)
        assert (filewatcher.get_status() != None)


class MissingFilesTest(unittest.TestCase):
    def test_missing_json_file(self):
        # Check to make sure trying to use a missing json file raises an IOError.
        self.assertRaises(IOError, housekeeping_classes.construct_status_group_from_json, 'not_there.json', 60)

    def test_missing_filewatcher_file(self):
        # Check to make sure passing in a missing file into the filewatcher raises ValueError
        self.assertRaises(ValueError, housekeeping_classes.StatusFileWatcher, 'myfilewatcher', [], 'not_there_glob', 60)
