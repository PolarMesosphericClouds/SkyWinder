import copy

from nose.tools import assert_raises, assert_almost_equal

from skywinder.communication.short_status import (ShortStatusCamera, ShortStatusLeader, decode_one_byte_summary,
                                                  encode_one_byte_summary, status_string_from_raid_status_byte,
                                                  get_raid_status, get_short_status_message_id_and_timestamp)


def test_incomplete_status():
    ss = ShortStatusCamera()
    with assert_raises(RuntimeError):
        ss.encode()


def test_camera_encode():
    ss = ShortStatusCamera()
    ss.message_id = 0
    ss.timestamp = 123.133
    ss.leader_id = 0
    ss.uptime = 58858
    ss.load = 1231
    ss.watchdog_status = -600
    ss.downlink_queue_depth = 20
    ss.free_disk_root_mb = 123000
    ss.free_disk_var_mb = 127000
    ss.free_disk_data_1_mb = 123000
    ss.free_disk_data_2_mb = 123000
    ss.free_disk_data_3_mb = 123000
    ss.free_disk_data_4_mb = 123000
    ss.free_disk_data_5_mb = 123000
    ss.root_raid_status = 0x07
    ss.var_raid_status = 0x07
    ss.total_images_captured = 49494
    ss.camera_packet_resent = 0
    ss.camera_packet_missed = 0
    ss.camera_frames_dropped = 0
    ss.camera_timestamp_offset_us = 65
    ss.trigger_interval = 2
    ss.frame_rate_times_1000 = 6250
    ss.frames_per_burst = 2
    ss.exposure_us = 4774
    ss.focus_step = 2000
    ss.focus_max = 1034
    ss.aperture_times_100 = 123
    ss.auto_exposure_enabled = 1
    ss.max_percentile_threshold = 7000
    ss.min_peak_threshold = 8000
    ss.min_percentile_threshold = 1000
    ss.adjustment_step_size = 500
    ss.min_auto_exposure = 35
    ss.max_auto_exposure = 1000000
    ss.pressure = 101033.3
    ss.lens_wall_temp = 30
    ss.dcdc_wall_temp = 25
    ss.labjack_temp = 28
    ss.camera_temp = 50
    ss.ccd_temp = 53
    ss.rail_12_mv = 12000
    ss.cpu_temp = 70
    ss.sda_temp = 55
    ss.sdb_temp = 45
    ss.sdc_temp = 48
    ss.sdd_temp = 47
    ss.sde_temp = 46
    ss.sdf_temp = 77
    ss.sdg_temp = -12
    ss.battery_min_temp = -12
    ss.battery_max_temp = 12
    ss.battery_current_coarse = 455
    ss.battery_current_fine = 455
    ss.battery_voltage_1 = 27890
    ss.battery_voltage_2 = 27890
    ss.battery_charge_1 = 252
    ss.battery_charge_2 = 252
    original_values = ss._values.copy()
    result = ss.encode()
    message_id,timestamp = get_short_status_message_id_and_timestamp(result)
    assert message_id == original_values['message_id']
    assert_almost_equal(timestamp,original_values['timestamp'])
    ss = ShortStatusCamera(result)
    for key in list(original_values.keys()):
        assert_almost_equal(original_values[key], ss._values[key], places=1)

def test_short_status_message_timestamp():
    message_id,timestamp = get_short_status_message_id_and_timestamp('\x01')
    assert message_id == 1
    assert timestamp != timestamp # nan != nan by definition

def test_coerce():
    ss = ShortStatusCamera()
    ss.message_id = 0
    ss.timestamp = 123.133
    ss.uptime = 49383
    ss.load = 1231.1
    ss.watchdog_status = -600
    ss.leader_id = 0
    ss.downlink_queue_depth = 20
    ss.free_disk_root_mb = 12300000000  # intentionally > 2^32 to check clipping
    ss.free_disk_var_mb = 16400
    ss.free_disk_data_1_mb = 123000
    ss.free_disk_data_2_mb = 123000
    ss.free_disk_data_3_mb = 123000
    ss.free_disk_data_4_mb = 123000
    ss.free_disk_data_5_mb = 123000
    ss.root_raid_status = 0x07
    ss.var_raid_status = 0x07
    ss.total_images_captured = 49494
    ss.camera_packet_resent = 0
    ss.camera_packet_missed = 0
    ss.camera_frames_dropped = 0
    ss.camera_timestamp_offset_us = 65
    ss.trigger_interval = 2
    ss.frame_rate_times_1000 = 6250
    ss.frames_per_burst = 2
    ss.exposure_us = 4774
    ss.focus_step = 200000
    ss.focus_max = 1034
    ss.aperture_times_100 = 123
    ss.auto_exposure_enabled = 1
    ss.max_percentile_threshold = 7000
    ss.min_peak_threshold = 8000
    ss.min_percentile_threshold = 1000
    ss.adjustment_step_size = 500
    ss.min_auto_exposure = 35
    ss.max_auto_exposure = 1000000
    ss.pressure = 101033.3
    ss.lens_wall_temp = 300
    ss.dcdc_wall_temp = -225
    ss.labjack_temp = 28
    ss.camera_temp = 50
    ss.ccd_temp = 53
    ss.rail_12_mv = 12000
    ss.cpu_temp = 70
    ss.sda_temp = 55
    ss.sdb_temp = 45
    ss.sdc_temp = 48
    ss.sdd_temp = 47
    ss.sde_temp = 46
    ss.sdf_temp = 77
    ss.sdg_temp = -12
    ss.battery_min_temp = -12
    ss.battery_max_temp = 12
    ss.battery_current_coarse = 455
    ss.battery_current_fine = 455
    ss.battery_voltage_1 = 27890
    ss.battery_voltage_2 = 27890
    ss.battery_charge_1 = 252
    ss.battery_charge_2 = 252
    values = ss._values.copy()
    ss2 = ShortStatusCamera(ss.encode())
    assert ss2.free_disk_root_mb == 2 ** 32 - 2
    assert ss2.focus_step == 2 ** 16 - 2
    assert ss2.lens_wall_temp == 126
    assert ss2.dcdc_wall_temp == -128

    ss._values = values
    ss.timestamp = "hello"
    result = ss.decode(ss.encode())
    assert result['timestamp'] == 0


def test_sizes():
    ss = ShortStatusCamera()
    print("camera status size:", ss.encoded_size)
    assert ss.encoded_size <= 255
    ss = ShortStatusLeader()
    print("leader status size:", ss.encoded_size)
    assert ss.encoded_size <= 255


def test_dir():
    ss = ShortStatusCamera()
    dir(ss)


def test_non_existant_attribute():
    ss = ShortStatusCamera()
    with assert_raises(AttributeError):
        ss.asdfb = 45


def test_one_byte():
    for value in range(255):
        result = decode_one_byte_summary(value)
        new_byte = encode_one_byte_summary(**result)
        assert value == new_byte
    with assert_raises(ValueError):
        decode_one_byte_summary(1000)


def test_status_string_from_raid_status_byte():
    for status_byte in range(256):
        status_string, nominal = status_string_from_raid_status_byte(status_byte)
        assert len(status_string) == 8
        if status_byte & 0x07 != 0x07:
            assert nominal is False
        elif status_byte & 0x78 != 0:
            assert nominal is False
        else:
            assert nominal is True


standard_mdstat_devices = {'md0': {'active': True,
                                   'bitmap': None,
                                   'disks': {'sdb1': {'faulty': False,
                                                      'number': 2,
                                                      'replacement': False,
                                                      'spare': False,
                                                      'write_mostly': True},
                                             'sdc1': {'faulty': False,
                                                      'number': 3,
                                                      'replacement': False,
                                                      'spare': False,
                                                      'write_mostly': True},
                                             'sdd1': {'faulty': False,
                                                      'number': 0,
                                                      'replacement': False,
                                                      'spare': False,
                                                      'write_mostly': False}},
                                   'personality': 'raid1',
                                   'read_only': False,
                                   'resync': None,
                                   'status': {'blocks': 9756672,
                                              'non_degraded_disks': 3,
                                              'raid_disks': 3,
                                              'super': '1.2',
                                              'synced': [True, True, True]}},
                           'md1': {'active': True,
                                   'bitmap': None,
                                   'disks': {'sdb2': {'faulty': False,
                                                      'number': 4,
                                                      'replacement': False,
                                                      'spare': False,
                                                      'write_mostly': True},
                                             'sdc2': {'faulty': False,
                                                      'number': 3,
                                                      'replacement': False,
                                                      'spare': False,
                                                      'write_mostly': True},
                                             'sdd2': {'faulty': False,
                                                      'number': 0,
                                                      'replacement': False,
                                                      'spare': False,
                                                      'write_mostly': False}},
                                   'personality': 'raid1',
                                   'read_only': False,
                                   'resync': None,
                                   'status': {'blocks': 20635648,
                                              'non_degraded_disks': 3,
                                              'raid_disks': 3,
                                              'super': '1.2',
                                              'synced': [True, True, True]}},
                           'md2': {'active': True,
                                   'bitmap': None,
                                   'disks': {'sdd5': {'faulty': False,
                                                      'number': 0,
                                                      'replacement': False,
                                                      'spare': False,
                                                      'write_mostly': False}},
                                   'personality': 'raid1',
                                   'read_only': True,
                                   'resync': None,
                                   'status': {'blocks': 846272,
                                              'non_degraded_disks': 1,
                                              'raid_disks': 1,
                                              'super': '1.2',
                                              'synced': [True]}}}

renumbered_arrays_example_devices = {'md10': {'active': True,
                                              'bitmap': None,
                                              'disks': {'sdc1': {'faulty': False,
                                                                 'number': 2,
                                                                 'replacement': False,
                                                                 'spare': False,
                                                                 'write_mostly': True},
                                                        'sdd1': {'faulty': False,
                                                                 'number': 0,
                                                                 'replacement': False,
                                                                 'spare': False,
                                                                 'write_mostly': False}},
                                              'personality': 'raid1',
                                              'read_only': False,
                                              'resync': None,
                                              'status': {'blocks': 9756672,
                                                         'non_degraded_disks': 2,
                                                         'raid_disks': 3,
                                                         'super': '1.2',
                                                         'synced': [True, True, False]}},
                                     'md11': {'active': True,
                                              'bitmap': None,
                                              'disks': {'sdc2': {'faulty': False,
                                                                 'number': 2,
                                                                 'replacement': False,
                                                                 'spare': False,
                                                                 'write_mostly': True},
                                                        'sdd2': {'faulty': False,
                                                                 'number': 0,
                                                                 'replacement': False,
                                                                 'spare': False,
                                                                 'write_mostly': False}},
                                              'personality': 'raid1',
                                              'read_only': False,
                                              'resync': None,
                                              'status': {'blocks': 20630528,
                                                         'non_degraded_disks': 2,
                                                         'raid_disks': 3,
                                                         'super': '1.2',
                                                         'synced': [True, True, False]}},
                                     'md12': {'active': True,
                                              'bitmap': None,
                                              'disks': {'sdd5': {'faulty': False,
                                                                 'number': 0,
                                                                 'replacement': False,
                                                                 'spare': False,
                                                                 'write_mostly': False}},
                                              'personality': 'raid1',
                                              'read_only': True,
                                              'resync': None,
                                              'status': {'blocks': 845248,
                                                         'non_degraded_disks': 1,
                                                         'raid_disks': 1,
                                                         'super': '1.2',
                                                         'synced': [True]}}}


def test_get_raid_status():
    assert get_raid_status(_mock_devices=standard_mdstat_devices)['/'] == 0x07
    assert get_raid_status(_mock_devices=standard_mdstat_devices)['/var'] == 0x07
    devices = copy.deepcopy(standard_mdstat_devices)
    devices['md0']['read_only'] = True
    assert get_raid_status(_mock_devices=devices)['/'] == 0x0F
    devices['md0']['status']['synced'] = [False, True, False]
    assert get_raid_status(_mock_devices=devices)['/'] == 0x0A
    devices['md0']['disks']['sdc1']['faulty'] = True
    assert get_raid_status(_mock_devices=devices)['/'] & 0x70 != 0
    assert get_raid_status(_mock_devices=renumbered_arrays_example_devices)['/'] == 0x03
    assert get_raid_status(_mock_devices=renumbered_arrays_example_devices)['/var'] == 0x03
