import logging
import socket
import struct

import errno

from skywinder.communication import constants

logger = logging.getLogger(__name__)


class Uplink():
    def __init__(self, name, uplink_port):
        self.name = name
        self.uplink_port = uplink_port
        socket_ = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socket_.bind(('0.0.0.0', self.uplink_port))
        socket_.settimeout(0)
        self.uplink_socket = socket_
        self.sip_leftover_buffer = ''

    def get_sip_packets(self):
        try:
            data = self.uplink_socket.recv(2000)
        except socket.error as e:
            if e.errno != errno.EAGAIN:  # EAGAIN is expected when no data has been received because the socket is set to non-blocking.
                logger.exception("Unexpected exceception caught while receiving SIP packets")
            return []

        logger.debug('Received bytes on uplink: %r' % data)

        buffer = self.sip_leftover_buffer + data
        packets, self.sip_leftover_buffer = get_sip_uplink_packets_from_buffer(buffer)
        return packets


def get_sip_uplink_packets_from_buffer(buffer):
    start_character = chr(constants.SIP_START_BYTE)
    end_character = chr(constants.SIP_END_BYTE)
    packets = []
    remainder = ''
    while buffer:
        idx = buffer.find(start_character)
        if idx == -1:
            # This means a START_BYTE was not found
            # We are done processing - discard junk before first idx.
            break
        else:
            logger.debug("Found start byte at %d, advancing to this byte" % idx)
            buffer = buffer[idx:]
        if len(buffer) < 3:  # all valid packets are at least 3 bytes long, so we don't have enough bytes yet
            remainder = buffer
            break
        received_start_byte, id_byte = struct.unpack('>1B1B', buffer[:2])
        if not id_byte in constants.VALID_SIP_IDS:
            # If the id_byte is not valid, we cut off the junk and continue the loop.
            logger.error(
                "Received unexpected SIP message ID byte %02X. Advancing 2 bytes.\nCurrent received buffer is:\n%r" % (
                id_byte, buffer))
            buffer = buffer[2:]
            continue
        if id_byte == constants.SCIENCE_DATA_REQUEST_MESSAGE:
            if end_character == buffer[2]:
                logger.info("Found science data request packet")
                packets.append(buffer[:3])

            else:
                logger.error(
                    "Received science data request packet with invalid end byte.\nCurrently received buffer is:\n%r" % buffer)
            logger.debug("Advancing 1 bytes to next packet")
            buffer = buffer[1:]
            continue

        elif id_byte == constants.SCIENCE_COMMAND_MESSAGE:
            payload_length, = struct.unpack('>1B', buffer[2])
            if len(buffer[3:]) < payload_length + 1:
                logger.debug(
                    'Length of buffer %d insufficient to contain full science command packet with payload length %d.' % (
                    len(buffer),
                    payload_length))
                remainder = buffer
                break

            if buffer[3 + payload_length] == end_character:
                logger.info("Found science command packet")
                packets.append(buffer[:3 + payload_length + 1])
                buffer = buffer[3 + payload_length + 1:]
                continue
            else:
                logger.error(
                    "Received science command packet with invalid end byte.\nCurrently received buffer is:\n%r" % buffer)
                logger.debug('Advancing 1 byte')
                buffer = buffer[1:]  # presumed id or length byte could actually be a valid start byte,
                                     # so don't throw it away.
                continue
        elif id_byte == constants.GPS_POSITION_MESSAGE:
            gps_format = constants.GPS_POSITION_FORMAT
            len_gps_format = struct.calcsize(gps_format)
            if len(buffer) >= len_gps_format:
                dle, _id, longitude, latitude, altitude, status, etx = struct.unpack(gps_format,
                                                                                     buffer[:len_gps_format])
                if dle == constants.SIP_START_BYTE and _id == constants.GPS_POSITION_MESSAGE and etx == constants.SIP_END_BYTE:
                    logger.info("Found GPS position message with lat: %f lon: %f alt: %f status: %02X" % (latitude,
                                                                                                         longitude,
                                                                                                         altitude,
                                                                                                         status))
                    packets.append(buffer[:len_gps_format])
                    buffer = buffer[len_gps_format:]
                    continue
                else:
                    logger.debug("Buffer looks like the start of GPS position message, but isnt, so advancing one byte"
                                 "Got %r" % buffer[:len_gps_format])
                    buffer = buffer[1:]
            else:
                logger.debug("Buffer looks like the start of GPS position message but is too short")
                remainder = buffer
                break
        elif id_byte == constants.GPS_TIME_MESSAGE:
            gps_format = constants.GPS_TIME_FORMAT
            len_gps_format = struct.calcsize(gps_format)
            if len(buffer) >= len_gps_format:
                dle, _id, gps_time_of_week, gps_week_number, gps_time_offset, cpu_time, etx = struct.unpack(gps_format,
                                                                                                            buffer[:len_gps_format])
                if dle == constants.SIP_START_BYTE and _id == constants.GPS_TIME_MESSAGE and etx == constants.SIP_END_BYTE:
                    logger.info("Found GPS time message with time of week: %f week num: %d gps offset: %f cpu time: %f"%
                                (gps_time_of_week,
                                 gps_week_number,
                                 gps_time_offset,
                                 cpu_time))
                    packets.append(buffer[:len_gps_format])
                    buffer = buffer[len_gps_format:]
                    continue
                else:
                    logger.debug("Buffer looks like the start of GPS time message, but isnt, so advancing one byte."
                                 "Got %r" % buffer[:len_gps_format])
                    buffer = buffer[1:]
            else:
                logger.debug("Buffer looks like the start of GPS time message but is too short")
                remainder = buffer
                break
        elif id_byte == constants.MKS_PRESSURE_MESSAGE:
            mks_format = constants.MKS_PRESSURE_FORMAT
            len_mks_format = struct.calcsize(mks_format)
            if len(buffer) >= len_mks_format:
                dle, _id, mks_high, mks_mid, mks_low, etx = struct.unpack(mks_format, buffer[:len_mks_format])
                if dle == constants.SIP_START_BYTE and _id == constants.MKS_PRESSURE_MESSAGE and etx == constants.SIP_END_BYTE:
                    logger.info("Found MKS message with high: %d, mid: %d, low %d"%
                                (mks_high,mks_mid,mks_low))
                    packets.append(buffer[:len_mks_format])
                    buffer = buffer[len_mks_format:]
                    continue
                else:
                    logger.debug("Buffer looks like the start of MKS message, but isnt, so advancing one byte."
                                 "Got %r" % buffer[:len_mks_format])
                    buffer = buffer[1:]
            else:
                logger.debug("Buffer looks like the start of MKS message but is too short")
                remainder = buffer
                break
        else:
            logger.error("Received Unhandled SIP message with ID %02X.\nCurrent buffer is\n%r" % (id_byte, buffer))
            logger.debug("Advancing 1 byte")
            buffer = buffer[1:]
    return packets, remainder
