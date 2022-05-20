import os

import subprocess

import time
from nose.tools import assert_raises
import socket
from skywinder.utils.tests.test_config import BasicTestHarness
from copy import deepcopy
from skywinder.communication import lidar
import socketserver
import threading

test_data_file_path = os.path.join(os.path.split(__file__)[0], 'lidar_telemetry_chunk.raw')


def test_parse_lidar_packets():
    with open(test_data_file_path) as fh:
        data = fh.read()
    remainder = 'xxalsfksafldklasdkdkadlasdfasdfxx' + ('\x00' * 10) + data
    packets = []
    while True:
        last_len = len(remainder)
        packet, remainder = lidar.find_next_lidar_packet(remainder)
        if packet:
            packets.append(packet)
            print(packet.payload_length, packet.frame_counter)
        if len(remainder) == last_len:
            break
    print(len(packets))
    print(len(remainder))
    assert len(packets) == 3
    assert len(remainder) == 3719


def test_parse_lidar_packets_with_lots_of_junk_at_head():
    #Make sure we don't continously process a block of bad data with no start pattern at the head.
    with open(test_data_file_path) as fh:
        data = fh.read()
    remainder = 'o'*6000 + ('\x00' * 10) + data[:1000]
    original_length = len(remainder)
    packet, remainder = lidar.find_next_lidar_packet(remainder)
    print(original_length, len(remainder))
    assert len(remainder) < original_length - 6000

def test_shorter_than_header_lidar_packet():
    packet, remainder = lidar.find_next_lidar_packet('xx')
    assert packet is None
    assert remainder == 'xx'


def test_short_lidar_packet():
    test_data = 'xxabcdefghijklmop'
    packet, remainder = lidar.find_next_lidar_packet(test_data)
    assert packet is None
    assert remainder == test_data


class TestLidar(BasicTestHarness):
    def test_lidar_connect_failure(self):
        config = deepcopy(self.basic_config)
        lt = lidar.LidarTelemetry(config=config)
        print(lt.config)
        lt.connect()
        lt.close()

    def test_lidar_connect(self):
        config = deepcopy(self.basic_config)

        telemetry_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        telemetry_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        telemetry_socket.bind(config.LidarTelemetry.telemetry_address)
        telemetry_socket.listen(10)
        lt = lidar.LidarTelemetry(config=config)
        lt.connect()
        lt.close()

        telemetry_socket.close()

    def test_get_lidar_data_connection(self):
        config = deepcopy(self.basic_config)

        telemetry_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        telemetry_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        telemetry_socket.bind(config.LidarTelemetry.telemetry_address)
        telemetry_socket.listen(10)

        slow_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        slow_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        slow_socket.bind(('', config.LidarTelemetry.slow_telemetry_port))
        slow_socket.listen(10)
        lt = lidar.LidarTelemetry(config=config)
        lt.get_telemetry_data()
        telemetry_socket.close()
        slow_socket.close()

    def test_get_lidar_data_no_connection(self):
        config = deepcopy(self.basic_config)

        lt = lidar.LidarTelemetry(config=config)
        with assert_raises(RuntimeError):
            lt.get_telemetry_data()

    def test_get_lidar_data(self):
        config = deepcopy(self.basic_config)
        with open(test_data_file_path) as fh:
            data = fh.read()

        slow_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        slow_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        slow_socket.bind(('', config.LidarTelemetry.slow_telemetry_port))
        slow_socket.listen(10)

        class SimulatedLidarHandler(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.sendall(data)

        class SimulatedServer(socketserver.TCPServer):
            allow_reuse_address = True

        server = SimulatedServer(config.LidarTelemetry.telemetry_address, SimulatedLidarHandler)

        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        lt = lidar.LidarTelemetry(config=config)
        packet = lt.get_telemetry_data()
        assert packet is not None
        assert packet.payload_length == 5415
        assert packet.frame_counter == 6669
        packet = lt.get_telemetry_data()
        print('bytes remaining:', len(lt.data_in_progress))
        assert packet is not None
        assert packet.payload_length == 5415
        assert packet.frame_counter == 6670
        packet = lt.get_telemetry_data()
        assert packet is not None
        assert packet.payload_length == 5415
        assert packet.frame_counter == 6671
        packet = lt.get_telemetry_data()
        assert packet is None
        lt.close()
        slow_socket.close()
        server.shutdown()
        server.server_close()
        server_thread.join(1)

    def test_get_lidar_bad_data(self):
        config = deepcopy(self.basic_config)

        slow_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        slow_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        slow_socket.bind(('', config.LidarTelemetry.slow_telemetry_port))
        slow_socket.listen(10)

        class SimulatedLidarHandler(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.sendall('xxabcdefghijklmop')

        class SimulatedServer(socketserver.TCPServer):
            allow_reuse_address = True

        server = SimulatedServer(config.LidarTelemetry.telemetry_address, SimulatedLidarHandler)

        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        lt = lidar.LidarTelemetry(config=config)
        lt.get_telemetry_data()
        lt.close()
        slow_socket.close()
        server.shutdown()
        server.server_close()
        server_thread.join(1)

    # the following test is not quite ready to run yet
    def t_get_slow_telemetry_data(self):
        config = deepcopy(self.basic_config)
        config.LidarTelemetry.telemetry_socket_timeout = 1.0

        slow_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        slow_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        slow_socket.bind(('', config.LidarTelemetry.slow_telemetry_port))
        slow_socket.listen(10)

        slow_status_data = 'hello' * 50

        class SimulatedLidarHandler(socketserver.BaseRequestHandler):
            def handle(self):
                print(repr(slow_socket.getpeername()))
                slow_socket.send(slow_status_data)

        class SimulatedServer(socketserver.TCPServer):
            allow_reuse_address = True

        server = SimulatedServer(config.LidarTelemetry.telemetry_address, SimulatedLidarHandler)

        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        lt = lidar.LidarTelemetry(config=config)
        lt.connect()
        slow_status = lt.request_and_get_slow_telemetry()
        time.sleep(1)
        # print repr(slow_status)
        assert slow_status == slow_status_data
        ping_status = lt.ping()
        time.sleep(1)
        # print repr(slow_status)
        assert ping_status == slow_status_data
        lt.close()
        server.shutdown()
        server.server_close()
        server_thread.join(1)
        slow_socket.close()
