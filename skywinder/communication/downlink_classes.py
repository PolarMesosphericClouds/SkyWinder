

import logging
import socket
import struct
import time

import numpy as np
from skywinder.communication import packet_classes

logger = logging.getLogger(__name__)


class HirateDownlink():
    def __init__(self, ip, port, speed_bytes_per_sec, name):
        self.downlink_ip, self.downlink_port = ip, port
        self.downlink_speed_bytes_per_sec = speed_bytes_per_sec
        self.prev_packet_size = 0
        self.prev_packet_time = 0
        self.total_bytes_sent = 0
        self.packets_to_send = []
        self.name = name
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


    def set_bandwidth(self,bytes_per_sec):
        self.downlink_speed_bytes_per_sec = bytes_per_sec
        logger.info("Set link %s bandwidth to %d bytes per second, %.2f kbps" % (self.name,
                                                                                 bytes_per_sec,
                                                                                 (bytes_per_sec/100.))) # 100 because 1000 bits / 10 bits per byte

    def put_data_into_queue(self, buffer, file_id, packet_size=1000, preempt=False):
        logger.debug('Buffer length: %d in downlink %s' % (len(buffer), self.name))
        packets = []
        num_packets = int(np.ceil(len(buffer) / packet_size))
        for i in range(num_packets):
            msg = buffer[(i * packet_size):((i + 1) * packet_size)]
            packet = packet_classes.FilePacket(file_id=file_id, packet_number=i,
                                               total_packet_number=num_packets, payload=msg)
            packets.append(packet)
        packet_length_debug_string = ','.join([str(packet.payload_length) for packet in packets])
        logger.debug('Packet payload lengths: %s for downlink %s' % (packet_length_debug_string, self.name))
        if preempt:
            self.packets_to_send = packets + self.packets_to_send
        else:
            self.packets_to_send = self.packets_to_send + packets


    def send_data(self):
        if not self.packets_to_send:
            logger.debug('No packets to send in downlink %s.' % self.name)
            return
        if self.downlink_speed_bytes_per_sec == 0:
            logger.debug("link %s is disabled, not sending data")
            return
        wait_time = self.prev_packet_size / self.downlink_speed_bytes_per_sec
        if time.time() - self.prev_packet_time > wait_time:
            buffer = self.packets_to_send[0].to_buffer()
            self.send(buffer, self.downlink_ip, self.downlink_port)
            self.prev_packet_size = len(buffer)
            self.prev_packet_time = time.time()
            self.packets_to_send = self.packets_to_send[1:]

    def send(self, msg, ip, port):
        bytes_sent = self.sock.sendto(msg, (ip, port))
        self.total_bytes_sent += bytes_sent
        logger.debug('Bytes sent on hirate downlink %s: %d' % (self.name, bytes_sent))

    def has_bandwidth(self):
        return (not self.packets_to_send) and self.enabled

    @property
    def enabled(self):
        return (self.downlink_speed_bytes_per_sec > 0)

    def flush_packet_queue(self):
        num_items = len(self.packets_to_send)
        self.packets_to_send = []
        logger.info("Flushed %d packets from downlink %s" % (num_items, self.name))


class LowrateDownlink():
    HEADER = b'\x10\x53'
    FOOTER = b'\x03'

    def __init__(self, name, downlink_ip, downlink_port):
        self.name = name
        self.downlink_ip, self.downlink_port = downlink_ip, downlink_port

    def _send(self, msg):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(msg, (self.downlink_ip, self.downlink_port))
        logger.debug("%s: Sending %d bytes %r to %s:%d" % (self.name, len(msg), msg, self.downlink_ip,self.downlink_port))
        sock.close()

    def send(self, msg):
        if len(msg) > 255:
            logger.critical("Attempt to send %d length packet on lowrate downlink. Truncating to 255 bytes" % len(msg))
            msg = msg[:255]
        packed_length = struct.pack('>1B', len(msg))
        msg = self.HEADER + packed_length + msg + self.FOOTER
        self._send(msg)

    def send_gps_mks_request(self):
        messages = ['\x10\x50\x03', # GPS Position (3.1.4.1)
                        '\x10\x51\x03', # GPS Time (3.1.4.2)
                        '\x10\x52\x03', # MKS Altitude (3.1.4.3)
                        ]
        self._send(''.join(messages))
