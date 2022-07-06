import time
from collections import OrderedDict
import numpy as np
from skywinder.utils.struct_formats import format_description
from skywinder.communication.short_status import status_string_from_raid_status_byte, ShortStatusCamera


def get_nan_value_for_short_status_field(field_name, class_=ShortStatusCamera):
    format_ = class_.item_table[field_name]
    description = format_description[format_]
    max_value = None
    # this is hacky, but we don't want to coerce the status_byte_ values because 0xFF is a valid status byte
    if ('int' in description) and not ('status_byte' in field_name):
        iinfo = np.iinfo(eval('np.%s' % description))
        max_value = iinfo.max  # we use iinfo.max to represent NaN
    return max_value


def format_short_status_camera(name, value):
    if name in list(short_status_camera_format_table.keys()):
        nan_value = get_nan_value_for_short_status_field(name)
        if value == nan_value:
            return '---', 'r'
        return short_status_camera_format_table[name](value)
    else:
        return ('Unknown: %r' % value), 'r'


def format_default(value):
    return str(value), ''


def format_timestamp(value):
    result = time.strftime("%H:%M:%S", time.localtime(value))
    ago = time.time() - value
    result += '  -%d s' % ago
    return result, ''


def format_uptime(value):
    days, seconds = divmod(value, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return '%dd %02d:%02d:%02d' % (days, hours, minutes, seconds), ''


def format_watchdog_status(value):
    if value < 500:
        format_string = 'r'
    else:
        format_string = ''
    return str(value), format_string


def format_camera_timestamp_offset(value):
    if abs(value) > 2000:
        format_string = 'r'
    else:
        format_string = ''
    return value, format_string


def format_frame_rate(value):
    frame_rate = value / 1000.
    try:
        interval_ms = 1000. / frame_rate
    except ZeroDivisionError as e:
        interval_ms = 0.0

    if frame_rate > 8.0:
        format_string = 'r'
    elif interval_ms == 0.0:
        format_string = 'r'
    else:
        format_string = ''

    return "%.3f (%.1f ms)" % (frame_rate, interval_ms), format_string


def format_disk_space(value):
    if value < 500:
        format_string = 'r'
    else:
        format_string = ''
    return str(value), format_string


def format_focus_step(value):
    if value < 500:
        format_string = 'r'
    else:
        format_string = ''
    return str(value), format_string


def format_temp(value):
    if value > 60:
        format = 'r'
    elif value <= 0:
        format = 'b'
    else:
        format = ''
    return str(value), format


def format_pressure(value):
    kpa = (value / 4.8 + 0.04) / 0.004
    if kpa < 100:
        format = 'r'
    else:
        format = ''
    return '%.2f' % kpa, format


def format_12v_rail(value):
    voltage = value / 1000.
    if voltage > 12.25 or voltage < 11.75:
        format = 'r'
    else:
        format = ''
    return '%.3f' % (voltage), format


def format_aperture(value):
    return '%.2f' % (value / 100.), ''


def format_battery_charge(value):
    percent = 100. * value / 254.
    if percent < 40.:
        format_string = 'r'
    else:
        format_string = ''
    return '%.1f' % (percent), format_string

def format_battery_voltage(value):
    voltage = value/1000.
    if voltage < 24:
        format = 'r'
    elif voltage > 24 and voltage < 25:
        format = 'm'
    elif voltage > 29:
        format = 'r'
    else:
        format = 'k'
    voltage = '%.3f' % voltage
    return voltage, format


def format_battery_current(value):
    if (value < -500 and value >= -9999):
        format_string = 'g'
    elif value < -9999.:
        format_string = 'r'
    elif value > 500.:
        format_string = 'm'
    else:
        format_string = ''
    return str(value), format_string


def format_raid_status(value):
    status_string, nominal = status_string_from_raid_status_byte(value)
    if nominal:
        format_string = ''
    else:
        format_string = 'r'
    return status_string, format_string


short_status_camera_format_table = OrderedDict([
    ("message_id", format_default),
    ("timestamp", format_timestamp),
    ("uptime", format_uptime),
    ("load", format_default),
    ("watchdog_status", format_watchdog_status),
    ("leader_id", format_default),
    ("downlink_queue_depth", format_default),

    ("free_disk_root_mb", format_disk_space),
    ("free_disk_var_mb", format_disk_space),
    ("free_disk_data_1_mb", format_disk_space),
    ("free_disk_data_2_mb", format_disk_space),
    ("free_disk_data_3_mb", format_disk_space),
    ("free_disk_data_4_mb", format_disk_space),
    ("free_disk_data_5_mb", format_disk_space),
    ("root_raid_status", format_raid_status),
    ("var_raid_status", format_raid_status),

    ("total_images_captured", format_default),
    ("camera_packet_resent", format_default),
    ("camera_packet_missed", format_default),
    ("camera_frames_dropped", format_default),
    ("camera_timestamp_offset_us", format_default),

    ("trigger_interval", format_default),
    ("frame_rate_times_1000", format_frame_rate),
    ("frames_per_burst", format_default),
    ("exposure_us", format_default),
    ("focus_step", format_focus_step),
    ("focus_max", format_default),
    ("aperture_times_100", format_aperture),

    ("auto_exposure_enabled", format_default),
    ("max_percentile_threshold", format_default),
    ("min_peak_threshold", format_default),
    ("min_percentile_threshold", format_default),
    ("adjustment_step_size", format_default),
    ("min_auto_exposure", format_default),
    ("max_auto_exposure", format_default),

    ("pressure", format_pressure),
    ("lens_wall_temp", format_temp),
    ("dcdc_wall_temp", format_temp),
    ("labjack_temp", format_temp),
    ("camera_temp", format_temp),
    ("ccd_temp", format_temp),
    ("rail_12_mv", format_12v_rail),
    ("cpu_temp", format_temp),
    ("sda_temp", format_temp),
    ("sdb_temp", format_temp),
    ("sdc_temp", format_temp),
    ("sdd_temp", format_temp),
    ("sde_temp", format_temp),
    ("sdf_temp", format_temp),
    ("sdg_temp", format_temp),

    ("battery_min_temp", format_temp),
    ("battery_max_temp", format_temp),
    ("battery_current_coarse", format_battery_current),
    ("battery_current_fine", format_battery_current),
    ("battery_voltage_1", format_battery_voltage),
    ("battery_voltage_2", format_battery_voltage),
    ("battery_charge_1", format_battery_charge),
    ("battery_charge_2", format_battery_charge),
])


def get_item_name(name):
    if name == 'rail_12_mv':
        return '12V rail'
    if name == 'aperture_times_100':
        return 'aperture'
    if name == 'frame_rate_times_1000':
        return 'frame_rate'
    return str(name).replace('_', ' ')
