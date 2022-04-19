"""
        telemetry format:
                struct frame_header {
                        uint16_t        start_marker;   // 0x78 0x78
                        uint16_t        frame_counter;
                        uint8_t         frame_type;
                        uint32_t        onboard_time;   // 20 bits onboard_time,
                                                        // 12 bits data_length
                        uint8_t         data_length;    // 12+8 = 20 bits data_length
                        uint16_t        crc;
                };
                and payload:
                        data_length = 5315 byte for telemetry mode 1
                        data_length = 5415 byte for telemetry mode 2
                        sizes may change in future

"""
import socket
import numpy as np
from traitlets import Int, TCPAddress, Float
from skywinder.utils.configuration import GlobalConfiguration
import logging
from skywinder.communication.packet_classes import LidarTelemetryPacket, PacketInsufficientLengthError, \
    PacketChecksumError

logger = logging.getLogger(__name__)

slow_telemetry_request = """0,A,T
0 COLOSSUS:SLOWTEL
END 48630
"""

lidar_ping_request = """0,A,T
0 COLOSSUS:PING
END 2432
"""


class LidarTelemetry(GlobalConfiguration):
    telemetry_address = TCPAddress(default_value=('lidar', 7007)).tag(config=True)
    slow_telemetry_port = Int(7008, min=1024, max=65535).tag(config=True)
    telemetry_socket_connection_timeout = Float(default_value=1.0,min=0).tag(config=True)
    telemetry_socket_data_timeout = Float(default_value=0.01,min=0).tag(config=True)

    def __init__(self, **kwargs):
        super(LidarTelemetry, self).__init__(**kwargs)
        self.telemetry_socket = None
        self.slow_telemetry_socket = None
        self.data_in_progress = ''
        self.latest_lidar_packet = None

    def connect(self):
        try:
            self.telemetry_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.telemetry_socket.settimeout(self.telemetry_socket_connection_timeout)
            self.telemetry_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.telemetry_socket.connect(self.telemetry_address)
            self.telemetry_socket.settimeout(self.telemetry_socket_data_timeout)
            self.slow_telemetry_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.slow_telemetry_socket.settimeout(self.telemetry_socket_connection_timeout)
            self.slow_telemetry_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.slow_telemetry_socket.connect((self.telemetry_address[0],self.slow_telemetry_port))
            self.slow_telemetry_socket.settimeout(self.telemetry_socket_data_timeout)
        except socket.error:
            logger.exception("Couldn't open sockets for telemetry address %r and slow telemetry port %d" %
                             (self.telemetry_address, self.slow_telemetry_port))
            self.close()

    def close(self):
        if self.telemetry_socket:
            try:
                self.telemetry_socket.close()
            except Exception as e:  # pragma: no cover
                logger.exception("Failure while closing telemetry socket")  # pragma: no cover
            self.telemetry_socket = None
        if self.slow_telemetry_socket:
            try:
                self.slow_telemetry_socket.close()
            except Exception as e:  # pragma: no cover
                logger.exception("Failure while closing slow telemetry socket")  # pragma: no cover
            self.slow_telemetry_socket = None

    def send_lidar_command(self, command):
        if self.telemetry_socket is None:
            logger.info("Lidar telemetry socket not connected, trying to connect first")
            self.connect()
            if self.telemetry_socket is None:
                raise RuntimeError("Unable to connect to LIDAR telemetry socket")
        try:
            self.telemetry_socket.sendall(command)
        except socket.error:
            logger.exception("Failed to send LIDAR command %r" % command)
            self.close()
        logger.info("Sent lidar command\n%r" % command)

    def get_telemetry_data(self):
        if self.telemetry_socket is None:
            logger.info("Lidar telemetry socket not connected, trying to connect first")
            self.connect()
            if self.telemetry_socket is None:
                raise RuntimeError("Unable to connect to LIDAR telemetry socket")
        try:
            data = self.telemetry_socket.recv(2 ** 20)
        except socket.timeout:
            data = ''
        except socket.error as e:
            logger.exception("Error while trying to receive telemetry")
            data = ''

        if not self.data_in_progress + data:
            return None
        lidar_packet, remainder = find_next_lidar_packet(self.data_in_progress + data)
        self.data_in_progress = remainder
        if lidar_packet is not None:
            logger.info("got valid packet from single TCP packet %d, %d" %
                        (lidar_packet.frame_counter, lidar_packet.payload_length))
            self.latest_lidar_packet = lidar_packet
        return lidar_packet

    def _get_slow_telemetry_data(self):
        try:
            packet = self.slow_telemetry_socket.recv(8192)
        except socket.error as e:
            print("no slow data", e)
            return None
        return packet

    def request_and_get_slow_telemetry(self):
        if self.telemetry_socket is None:
            logger.info("Lidar telemetry socket not connected, trying to connect first")
            self.connect()
            if self.telemetry_socket is None:
                raise RuntimeError("Unable to connect to LIDAR telemetry socket")
        self.send_lidar_command(slow_telemetry_request)
        return self._get_slow_telemetry_data()

    def ping(self):
        if self.telemetry_socket is None:
            logger.info("Lidar telemetry socket not connected, trying to connect first")
            self.connect()
            if self.telemetry_socket is None:
                raise RuntimeError("Unable to connect to LIDAR telemetry socket")
        self.send_lidar_command(lidar_ping_request)
        result = self._get_slow_telemetry_data()
        logger.info("Ping lidar returned %r" % result)
        return result


    def run(self): # Only used for initial test, not used elsewhere, so no need for coverage.
        if self.telemetry_socket is None:  # pragma: no cover
            self.connect()  # pragma: no cover
        while True:  # pragma: no cover
            print(self.request_and_get_slow_telemetry())  # pragma: no cover


def find_next_lidar_packet(data, start_pattern='xx'):
    if len(data) < LidarTelemetryPacket.header_length:
        logger.debug("Data length %d is too short to contain header of length %d" % (len(data), LidarTelemetryPacket.header_length))
        return None,data
    remainder = data
    while True:
        start_index = remainder.find(start_pattern)
        if start_index < 0:
            logger.debug("No start pattern found")
            return None, remainder
        if start_index > 0:
            logger.warning("dropping %d bytes preceeding first valid start pattern" % start_index)
            remainder = remainder[start_index:]
        try:
            header_length = LidarTelemetryPacket.header_length
            header = LidarTelemetryPacket.decode_header(remainder[:header_length])
            packet_length = header_length + header['data_length']
            packet = LidarTelemetryPacket(buffer=remainder[:packet_length])
            logger.info("Found lidar telemetry packet starting at index %d" % start_index)
            return packet, remainder[packet_length:]
        except PacketInsufficientLengthError:
            logger.debug("Data too short to include a packet, expected length is %d"%packet_length)
            if len(remainder[1:]) > LidarTelemetryPacket.header_length:
                logger.debug("Recursively searching for packet starting at index %d of %d" % (1,len(remainder)))
                trial_packet,trial_remainder = find_next_lidar_packet(remainder[1:],start_pattern=start_pattern)
                if trial_packet:
                    logger.debug("Found packet using recursion")
                    return trial_packet,trial_remainder
            return None, remainder
        except PacketChecksumError:
            logger.exception("Encountered bad data (failed checksum), advancing 1 byte")
            remainder = remainder[1:]
        except Exception:
            logger.exception("Failed to decode candidate packet at index %d, advancing 1 byte" % start_index)
            remainder = remainder[1:]


if __name__ == "__main__":
    lt = LidarTelemetry()
    lt.run()
