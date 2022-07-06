from traitlets import (Int, Unicode, Bytes, List, Float, Enum, TCPAddress, Dict)
from traitlets.config import Configurable

standard_baudrates = (1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 500000, 576000, 921600, 1000000)
openport_origin_ip = '%d.%d.%d.%d' % (0x80, 0x3b, 0xa8, 0x4e)

class GroundConfiguration(Configurable):
    root_data_path = Bytes('/data/gse_data').tag(config=True)
    command_history_subdir = Bytes('command_history').tag(config=True)
    command_index_filename = Bytes('index.csv').tag(config=True)
    openport_uplink_addresses = List(TCPAddress(('pmc-camera-4',5001), help="(IP,port) tuple to send OpenPort commands to")).tag(config=True)
    openport_origin_address = TCPAddress((openport_origin_ip,0)).tag(config=True)
    command_port = Bytes('/dev/ttyUSB1', help="Serial device connected to GSE uplink").tag(config=True)

    downlink_parameters = Dict(default_value=dict(openport=dict(port=4502,baudrate=None,loop_interval=1.0),
                                                  gse_sip=dict(port='/dev/ttyUSB0',baudrate=115200, loop_interval=0.2),
                                                  los=dict(port='/dev/ttyS0',baudrate=115200, loop_interval=0.2),
                                                  tdrss_direct=dict(port='/dev/ttyUSB2',baudrate=115200,loop_interval=0.2))).tag(config=True)

    lidar_command_relay_address = TCPAddress(default_value=('0.0.0.0',7100),
                                   help = "Interface and port number to listen on for lidar commands to be forwarded").tag(config=True)

    lidar_downlink_forwarding_listen_address = TCPAddress(default_value=('0.0.0.0',7101), min=1024, max=65535,
                                         help="Interface and port to listen to forward lidar data frames").tag(config=True)

