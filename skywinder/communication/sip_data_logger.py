import os
import struct
import logging
import time

from skywinder.utils.housekeeping_logger import HousekeepingLogger
from skywinder.communication import constants
logger = logging.getLogger(__name__)

class SipDataLogger(object):
    def __init__(self, sip_logging_dir):
        gps_position_logging_dir = os.path.join(sip_logging_dir, 'gps_position')
        gps_time_logging_dir = os.path.join(sip_logging_dir, 'gps_time')
        mks_logging_dir = os.path.join(sip_logging_dir, 'mks_data')
        self.gps_position_logger = HousekeepingLogger(columns = ['epoch', 'longitude', 'latitude', 'altitude', 'status', 'link_name'],
                                                      formats = ['%f', '%f', '%f', '%f', '%d', '%s'],
                                                      housekeeping_dir=gps_position_logging_dir)

        self.gps_time_logger = HousekeepingLogger(columns = ['epoch', 'gps_time_of_week', 'gps_week_number', 'gps_time_offset', 'cpu_time', 'link_name'],
                                                      formats = ['%f', '%f', '%d', '%f', '%f', '%s'],
                                                      housekeeping_dir=gps_time_logging_dir)

        self.mks_logger = HousekeepingLogger(columns = ['epoch', 'mks_high', 'mks_mid', 'mks_low', 'link_name'],
                                                      formats = ['%f', '%d', '%d', '%d', '%s'],
                                                      housekeeping_dir=mks_logging_dir)

        self.gps_position_logger.create_log_file()
        self.gps_time_logger.create_log_file()
        self.mks_logger.create_log_file()

    def log_sip_data_packet(self, packet, link_name):
        epoch = time.time()
        dle, id_byte = struct.unpack(">2B", packet[:2])
        if id_byte == constants.GPS_POSITION_MESSAGE:
            dle, _id, longitude, latitude, altitude, status, etx = struct.unpack(constants.GPS_POSITION_FORMAT,packet)
            self.gps_position_logger.write_log_entry(dict(epoch=epoch, longitude=longitude, latitude=latitude,
                                                          altitude=altitude, status=status, link_name=link_name))
            return
        if id_byte == constants.GPS_TIME_MESSAGE:
            dle, _id, gps_time_of_week, gps_week_number, gps_time_offset, cpu_time, etx = struct.unpack(constants.GPS_TIME_FORMAT,
                                                                                                        packet)
            self.gps_time_logger.write_log_entry(dict(epoch=epoch, gps_time_of_week=gps_time_of_week,
                                                      gps_week_number=gps_week_number, gps_time_offset=gps_time_offset,
                                                      cpu_time=cpu_time, link_name=link_name))
            return
        if id_byte == constants.MKS_PRESSURE_MESSAGE:
            dle, _id, mks_high, mks_mid, mks_low, etx = struct.unpack(constants.MKS_PRESSURE_FORMAT, packet)
            self.mks_logger.write_log_entry(dict(epoch=epoch, mks_high=mks_high, mks_mid=mks_mid, mks_low=mks_low,
                                                 link_name=link_name))
            return
        logger.error("Found unknown id_byte %d for packet %r" % (id_byte, packet))

