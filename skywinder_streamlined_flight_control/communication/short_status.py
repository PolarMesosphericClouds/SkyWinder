from collections import OrderedDict
import struct

import skywinder_streamlined_flight_control.communication.file_format_classes
import skywinder_streamlined_flight_control.communication.packet_classes
from skywinder_streamlined_flight_control.utils.struct_formats import format_description
import numpy as np
import logging

logger = logging.getLogger(__name__)

try:
    import mdstat
except ImportError:
    logger.warning("Cannot import mdstat, used to populate RAID status.")


def coerce_value(value, description):
    return eval('np.%s(%r)' % (description, value))


class ShortStatusBase(object):
    item_table = OrderedDict([("example", 'B')])

    def __init__(self, buffer_to_decode=None):
        self._values = OrderedDict()
        self.reset_values()
        if buffer_to_decode is not None:
            self._values = self.decode(buffer_to_decode)

    def reset_values(self):
        self._values = OrderedDict([(name, None) for name in list(self.item_table.keys())])

    def __dir__(self):
        return list(self.item_table.keys()) + ['encoded_size', 'encode', 'decode', 'values']

    def __setattr__(self, key, value):
        if key == '_values':
            return super(ShortStatusBase, self).__setattr__(key, value)
        if key in self._values:
            self._values[key] = value
        else:
            raise AttributeError("Attempting to set non-existant key %r to %s" % (key, value))

    def __getattr__(self, item):
        try:
            return super(ShortStatusBase, self).__getattribute__(item)
        except AttributeError:
            return self._values[item]

    @property
    def values(self):
        return self._values

    @property
    def encoded_size(self):
        return struct.calcsize('>' + ''.join([format_ for name, format_ in list(self.item_table.items())]))

    def encode(self):
        result = []
        for name, value in list(self._values.items()):
            if value is None:
                logger.critical("Attempt to encode status before all values have been set. Missing value for %s" % name)
                raise RuntimeError("Cannot encode status before all values have been set. Missing value for %s" % name)
            format_ = self.item_table[name]
            description = format_description[format_]
            # this is hacky, but we don't want to coerce the status_byte_ values because 0xFF is a valid status byte
            if ('int' in description) and not ('status_byte' in name):
                iinfo = np.iinfo(eval('np.%s' % description))
                max_value = iinfo.max - 1  # maximum valid value, we use iinfo.max to represent NaN
                if value < iinfo.min:
                    logger.warning("Clipping %s from %r to %d" % (name, value, iinfo.min))
                    coerced_value = iinfo.min
                elif value > max_value:
                    logger.warning("Clipping %s from %r to %d" % (name, value, max_value))
                    coerced_value = max_value
                else:
                    try:
                        coerced_value = coerce_value(value, description)
                    except (ValueError, NameError):
                        # This likely means the value is a nan. for now, represent that as max value
                        if value == value:  # this will not be true if value is nan
                            logger.warning("Invalid value %r encountered for parameter %s with format '%s'"
                                           % (value, name, format_))
                        coerced_value = iinfo.max
            else:
                coerced_value = value

            try:
                formatted_value = struct.pack('>' + format_, coerced_value)
            except Exception:
                logger.exception("Failed to pack %s value %r" % (name, coerced_value))
                formatted_value = struct.pack('>' + format_, 0)
            result.append(formatted_value)
        self.reset_values()
        return ''.join(result)

    def decode(self, buffer_to_decode):
        format_string = '>' + ''.join([format_ for name, format_ in list(self.item_table.items())])
        values = struct.unpack(format_string, buffer_to_decode)
        return OrderedDict(list(zip(list(self.item_table.keys()), values)))


class ShortStatusLeader(ShortStatusBase):
    item_table = OrderedDict([("message_id", "B"),
                              ("timestamp", "d"),
                              ("leader_id", "B"),

                              ("status_byte_camera_0", "B"),
                              ("status_byte_camera_1", "B"),
                              ("status_byte_camera_2", "B"),
                              ("status_byte_camera_3", "B"),
                              ("status_byte_camera_4", "B"),
                              ("status_byte_camera_5", "B"),
                              ("status_byte_camera_6", "B"),
                              ("status_byte_camera_7", "B"),
                              ("status_byte_lidar", "B"),
                              ("lidar_bytes_to_process", "I"),
                              ("max_lidar_files_per_poll", "B"),
                              ("use_synchronized_images", "B"),

                              ("last_command_sequence", "H"),
                              ("highest_command_sequence", "H"),
                              ("last_outstanding_sequence", "H"),
                              ("total_commands_received", "H"),
                              ("last_failed_sequence", "H"),
                              ("current_file_id", "I"),

                              ("bytes_sent_highrate", "I"),
                              ("bytes_sent_openport", "I"),
                              ("bytes_sent_los", "I"),
                              ("packets_queued_highrate", "B"),
                              ("packets_queued_openport", "B"),
                              ("packets_queued_los", "B"),
                              ("bytes_per_sec_highrate", "H"),
                              ("bytes_per_sec_openport", "H"),
                              ("bytes_per_sec_los", "H"),

                              ("charge_cont_1_solar_voltage", "h"),
                              ("charge_cont_1_solar_current", "h"),
                              ("charge_cont_1_battery_voltage", "h"),
                              ("charge_cont_1_battery_current", "h"),
                              ("charge_cont_1_battery_temp", "b"),
                              ("charge_cont_1_heatsink_temp", "b"),

                              ("charge_cont_2_solar_voltage", "h"),
                              ("charge_cont_2_solar_current", "h"),
                              ("charge_cont_2_battery_voltage", "h"),
                              ("charge_cont_2_battery_current", "h"),
                              ("charge_cont_2_battery_temp", "b"),
                              ("charge_cont_2_heatsink_temp", "b"),

                              ])
    LEADER_MESSAGE_ID = 254

    def reset_values(self):
        super(ShortStatusLeader, self).reset_values()
        self.message_id = self.LEADER_MESSAGE_ID


class ShortStatusCamera(ShortStatusBase):
    item_table = OrderedDict([("message_id", "B"),
                              ("timestamp", "d"),
                              ("uptime", "I"),
                              ("load", "H"),
                              ("watchdog_status", "h"),
                              ("leader_id", "B"),
                              ("downlink_queue_depth", "H"),

                              ("free_disk_root_mb", "I"),
                              ("free_disk_var_mb", "I"),
                              ("free_disk_data_1_mb", "I"),
                              ("free_disk_data_2_mb", "I"),
                              ("free_disk_data_3_mb", "I"),
                              ("free_disk_data_4_mb", "I"),
                              ("free_disk_data_5_mb", "I"),
                              ("root_raid_status", "B"),
                              ("var_raid_status", "B"),

                              ("total_images_captured", "I"),
                              ("camera_packet_resent", "I"),
                              ("camera_packet_missed", "I"),
                              ("camera_frames_dropped", "I"),
                              ("camera_timestamp_offset_us", "h"),

                              ("trigger_interval", "B"),
                              ("frame_rate_times_1000", "H"),
                              ("frames_per_burst", "B"),
                              ("exposure_us", "I"),
                              ("focus_step", "H"),
                              ("focus_max", "H"),
                              ("aperture_times_100", "H"),

                              ("auto_exposure_enabled", "B"),
                              ("max_percentile_threshold", "H"),
                              ("min_peak_threshold", "H"),
                              ("min_percentile_threshold", "H"),
                              ("adjustment_step_size", "H"),
                              ("min_auto_exposure", "I"),
                              ("max_auto_exposure", "I"),

                              ("pressure", "f"),
                              ("lens_wall_temp", 'b'),
                              ("dcdc_wall_temp", "b"),
                              ("labjack_temp", "b"),
                              ("camera_temp", "b"),
                              ("ccd_temp", "b"),
                              ("rail_12_mv", "H"),
                              ("cpu_temp", 'b'),
                              ("sda_temp", 'b'),
                              ("sdb_temp", 'b'),
                              ("sdc_temp", 'b'),
                              ("sdd_temp", 'b'),
                              ("sde_temp", 'b'),
                              ("sdf_temp", 'b'),
                              ("sdg_temp", 'b'),

                              ("battery_min_temp", 'b'),
                              ("battery_max_temp", 'b'),
                              ("battery_current_coarse", 'i'),
                              ("battery_current_fine", 'i'),
                              ("battery_voltage_1", 'i'),
                              ("battery_voltage_2", 'i'),
                              ("battery_charge_1", 'B'),
                              ("battery_charge_2", 'B'),
                              ])


one_byte_summary_bit_definitions = ['is_leader',
                                    'controller_alive',
                                    'pipeline_alive',
                                    'files_to_downlink',
                                    'ptp_synced',
                                    'time_synced',
                                    'taking_images',
                                    'writing_images']


def encode_one_byte_summary(is_leader, controller_alive, pipeline_alive, files_to_downlink, ptp_synced, time_synced,
                            taking_images, writing_images):
    result = 0
    result += int(is_leader) << one_byte_summary_bit_definitions.index('is_leader')
    result += int(controller_alive) << one_byte_summary_bit_definitions.index('controller_alive')
    result += int(pipeline_alive) << one_byte_summary_bit_definitions.index('pipeline_alive')
    result += int(files_to_downlink) << one_byte_summary_bit_definitions.index('files_to_downlink')
    result += int(ptp_synced) << one_byte_summary_bit_definitions.index('ptp_synced')
    result += int(time_synced) << one_byte_summary_bit_definitions.index('time_synced')
    result += int(taking_images) << one_byte_summary_bit_definitions.index('taking_images')
    result += int(writing_images) << one_byte_summary_bit_definitions.index('writing_images')
    return result


def decode_one_byte_summary(one_byte):
    if one_byte > 255 or one_byte < 0:
        raise ValueError("Cannot decode value outside of range 0-255, got %r" % one_byte)
    result = OrderedDict()
    for k in range(len(one_byte_summary_bit_definitions)):
        result[one_byte_summary_bit_definitions[k]] = bool((1 << k) & one_byte)
    return result


no_response_one_byte_status = encode_one_byte_summary(is_leader=False, controller_alive=False, pipeline_alive=True,
                                                      files_to_downlink=True, ptp_synced=False, time_synced=False,
                                                      taking_images=False,
                                                      writing_images=False)  # this value should be impossible to achieve naturally


def get_short_status_message_id_and_timestamp(payload):
    fmt = '>Bd' # message_id is uint8, timestamp is float64
    fmt_len = struct.calcsize(fmt)
    if len(payload) < fmt_len:
        message_id, = struct.unpack('>B',payload[0])
        timestamp = np.nan
    else:
        message_id,timestamp = struct.unpack(fmt, payload[:fmt_len])
    return message_id,timestamp


def load_short_status_from_file(filename):
    """
    Interpret file as GSE lowrate packet and convert payload to retrieve short status information

    Parameters
    ----------
    filename

    Returns
    -------
    ShortStatusCamera, ShortStatusLeader, or ShortStatusLidar as appropriate

    """
    gse_packet = skywinder_streamlined_flight_control.communication.packet_classes.load_gse_packet_from_file(filename)
    payload = gse_packet.payload
    return load_short_status_from_payload(payload)


def load_short_status_from_payload(payload):
    message_id,timestamp = get_short_status_message_id_and_timestamp(payload)
    if message_id == ShortStatusLeader.LEADER_MESSAGE_ID:
        return ShortStatusLeader(payload)
    elif message_id < 8:
        return ShortStatusCamera(payload)
    else:
        raise RuntimeError("Unsupported short status type")


raid_status_bit_definitions = ['unused',
                               'drive_3_faulty',
                               'drive_2_faulty',
                               'drive_1_faulty',
                               'read_only',
                               'drive_3_sync',
                               'drive_2_sync',
                               'drive_1_sync', ]


def get_raid_status(_mock_devices=None):
    if _mock_devices is None:
        devices = mdstat.parse()['devices']
    else:
        devices = _mock_devices
    results = {}
    volumes = list(devices.keys())
    volumes.sort()

    for mount_point, device in zip(['/', '/var'], volumes[:2]):
        status_byte = 0
        synced = devices[device]['status']['synced']
        for drive, drive_status in enumerate(synced):
            if drive_status:
                status_byte = status_byte + 2 ** (drive)
        if devices[device]['read_only']:
            status_byte += 0x08
        for drive, drive_status in enumerate(devices[device]['disks'].values()):
            if drive_status['faulty']:
                status_byte += 2 ** (drive + 4)
        results[mount_point] = status_byte
    return results


def status_string_from_raid_status_byte(status_byte):
    status_string = ''
    nominal = True
    for bit in range(0, 3):
        if (status_byte & (2 ** bit)) != 0:
            bit_status = 'U'
        else:
            bit_status = '_'
            nominal = False
        status_string = bit_status + status_string
    if status_byte & 0x08 != 0:
        status_string = 'R' + status_string
        nominal = False
    else:
        status_string = ' ' + status_string
    for bit in range(4, 7):
        if (status_byte & (2 ** bit)) != 0:
            bit_status = 'F'
            nominal = False
        else:
            bit_status = '_'
        status_string = bit_status + status_string
    if status_byte & 0x08 != 0:
        status_string = '1' + status_string
    else:
        status_string = ' ' + status_string
    return status_string, nominal
