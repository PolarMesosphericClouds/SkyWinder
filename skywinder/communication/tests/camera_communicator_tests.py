import collections
import shutil
import tempfile
import copy

import Pyro4
import time
from nose.tools import timed
from skywinder.communication import command_table
from skywinder.communication import packet_classes
from skywinder.communication import short_status

from skywinder.camera.pipeline import controller, basic_pipeline
from skywinder.communication import camera_communicator
from skywinder.utils.tests.test_config import BasicTestHarness
from copy import deepcopy

#from skywinder.utils.log import setup_stream_handler,logging
#setup_stream_handler(logging.DEBUG)

counter_dir = ''

FAKE_PYRO_PORT = 56654


def setup():
    global counter_dir
    counter_dir = tempfile.mkdtemp()


def teardown():
    global counter_dir
    shutil.rmtree(counter_dir)


class TestCommunicator(BasicTestHarness):
    def test_00_valid_command_table(self):
        config = deepcopy(self.basic_config)
        config.Communicator.lowrate_link_parameters = [('comm1', ('localhost', 6501), 6501)]
        cc = camera_communicator.Communicator(cam_id=0, peers={}, controller=None, pyro_port=FAKE_PYRO_PORT,
                                              start_pyro=False,  config=config)
        cc.validate_command_table()
        cc.close()

    # def test_failing_commands(self):
    #     config = copy.deepcopy(self.basic_config)
    #     config.BasicPipeline.default_write_enable = 1
    #     bpl = basic_pipeline.BasicPipeline(config=config)
    #
    #     bpl.initialize()
    #     time.sleep(2)
    #     cont = controller.Controller(pipeline=bpl, config=self.basic_config)
    #     config1 = deepcopy(self.basic_config)
    #     config1.Communicator.lowrate_link_parameters = [('comm1', ('localhost', 6501), 6501)]
    #     cc1 = camera_communicator.Communicator(cam_id=0, peers={}, controller=None, pyro_port=FAKE_PYRO_PORT,
    #                                            start_pyro=False, config=config1)
    #
    #     config2 = deepcopy(self.basic_config)
    #     config2.Communicator.lowrate_link_parameters = []#[('comm2', ('localhost', 6601), 6601)]
    #
    #     class SlowController(controller.Controller):
    #         def __getattr__(self, item):
    #             print  "getting SlowController attribute..."
    #             time.sleep(1)
    #             super(SlowController,self).__getattr__(item)
    #     cont2 = SlowController(pipeline=bpl, config=self.basic_config)
    #     cc2 = camera_communicator.Communicator(cam_id=1, peers={}, controller=cont2, pyro_port=FAKE_PYRO_PORT,
    #                                            start_pyro=False, config=config2)
    #     cc1.controller = cont
    #     cc2.controller = cont
    #     cc1.peers = collections.OrderedDict([(0, cc1), (1, cc2)])
    #     cc1.destination_lists = {0: [cc1], 1: [cc2]}
    #     cc1.set_peer_polling_order([0,1])
    #     cc1.get_next_data()
    #     cc1.get_next_data()
    #     cc1.get_next_data()
    #     cc1.get_next_data()
    def test_basic_command_path(self):
        config = copy.deepcopy(self.basic_config)
        config.BasicPipeline.default_write_enable = 1
        bpl = basic_pipeline.BasicPipeline(config=config)

        bpl.initialize()
        time.sleep(2)
        cont = controller.Controller(pipeline=bpl, config=self.basic_config)
        config1 = deepcopy(self.basic_config)
        config1.Communicator.lowrate_link_parameters = [('comm1', ('localhost', 6501), 6501)]
        cc1 = camera_communicator.Communicator(cam_id=0, peers={}, controller=None, pyro_port=FAKE_PYRO_PORT,
                                               start_pyro=False, config=config1)

        config2 = deepcopy(self.basic_config)
        config2.Communicator.lowrate_link_parameters = []#[('comm2', ('localhost', 6601), 6601)]
        cc2 = camera_communicator.Communicator(cam_id=1, peers={}, controller=None, pyro_port=FAKE_PYRO_PORT,
                                               start_pyro=False, config=config2)
        cc1.controller = cont
        cc2.controller = cont
        cc1.peers = collections.OrderedDict([(0, cc1), (1, cc2)])
        cc1.destination_lists = {0: [cc1], 1: [cc2]}
        command = command_table.command_manager.set_focus(focus_step=1000)
        command_packet = packet_classes.CommandPacket(payload=command, sequence_number=1, destination=1)
        cc1.execute_packet(command_packet.to_buffer(), lowrate_link_index=0)

        bad_buffer = command_packet.to_buffer()[:-2] + 'AA'
        cc1.execute_packet(bad_buffer, lowrate_link_index=0)

        bad_crc_buffer = command_packet.to_buffer()[:-2] + 'A\x03'
        cc1.execute_packet(bad_crc_buffer, lowrate_link_index=0)

        cc1.execute_packet('bad packet', lowrate_link_index=0)

        non_existant_command = '\xfe' + command
        cc1.execute_packet(packet_classes.CommandPacket(payload=non_existant_command, sequence_number=1,
                                                        destination=1).to_buffer(), lowrate_link_index=0)

        cm = command_table.command_manager
        commands = [cm.set_exposure(exposure_time_us=1000),
                    cm.run_focus_sweep(request_id=333,row_offset=1000, column_offset=1000, num_rows=256,num_columns=256,
                                       scale_by = 1.0, quality=90,start=4400,stop=4900,step=10),
                    cm.send_arbitrary_camera_command(command="TriggerSource:FixedRate"),
                    cm.send_arbitrary_camera_command(command="TriggerSource:None"),
                    cm.send_arbitrary_camera_command(command="TriggerSource:FixedRate:"),
                    cm.send_arbitrary_camera_command(command="TriggerSource"),
                    cm.set_standard_image_parameters(row_offset=1000, column_offset=1000, num_rows=256,num_columns=256,
                                       scale_by = 1.0, quality=90),
                    cm.set_peer_polling_order([0,1,2,3,4,5,6]),
                    cm.request_specific_file(max_num_bytes=2**20,request_id=123,filename='/data1/index.csv'),
                    cm.run_shell_command(max_num_bytes_returned=2**20,request_id=3488,timeout=30.0,command_line="ls -lhtr"),
#                    cm.run_shell_command(max_num_bytes_returned=2**20,request_id=3489,timeout=30.0,command_line="dd of=/dev/stdout if=/dev/random count=200"),
                    cm.get_status_report(compress=1,request_id=344),
                    cm.get_status_report(compress=0,request_id=344),
                    cm.get_status_report(compress=2,request_id=344),
                    cm.get_status_report(compress=3,request_id=344),
                    cm.flush_downlink_queues(),
                    cm.use_synchronized_images(synchronize=1),
                    cm.set_downlink_bandwidth(openport=10000,highrate=100,los=0),
                    cm.request_specific_images(timestamp=123456789.123,request_id=1223,num_images=2,step=1,row_offset=1000,
                                               column_offset=1000, num_rows=256,num_columns=256,
                                       scale_by = 1.0, quality=90),
                    cm.get_command_history(request_id=355,max_entries=0),
                    cm.get_command_history(request_id=355,max_entries=34),
                    cm.enable_auto_exposure(enabled=1),
                    cm.set_auto_exposure_parameters(max_percentile_threshold_fraction=0.9,
                                     min_peak_threshold_fraction=0.7,
                                     min_percentile_threshold_fraction=0.1,
                                     adjustment_step_size_fraction=0.05,
                                     min_exposure=35,
                                     max_exposure=1000000),
                    cm.request_blobs_by_timestamp(timestamp=123456789.123,request_id=1223,num_images=2,step=1,
                                                  stamp_size=20,blob_threshold=12, kernel_sigma=1, kernel_size=8,
                                                  cell_size=128, max_num_blobs=10, quality=75),
                    cm.set_trigger_interval(interval=4),
                    cm.set_max_lidar_files_per_poll(max_files=16),
                    cm.send_lidar_command(command="HELLO"),
                    cm.flush_lidar_data_backlog(),
                    ]
        for command in commands:
            print(cm.decode_commands(command))
            cc1.execute_packet(packet_classes.CommandPacket(payload=command, sequence_number=1,
                                                        destination=1).to_buffer(), lowrate_link_index=0)

        cc1.close()
        cc2.close()
        bpl.close()
        time.sleep(1)



class FakeLowrateUplink():
    def __init__(self):
        self.bytes = ''

    def assign_bytes_to_get(self, bytes):
        self.bytes = bytes

    def get_sip_packets(self):
        return [self.bytes]


class FakeLowrateDownlink():
    def __init__(self):
        self.buffer = '\xff'*255

    def send(self, msg):
        self.buffer = msg

    def retrieve_msg(self):
        return self.buffer


class FakeHirateDownlink():
    def __init__(self):
        self.queue = None

    def has_bandwidth(self):
        return True

    def put_data_into_queue(self, data, file_id):
        self.queue = data


class FakeController():
    def get_latest_fileinfo(self):
        return [0] * 20

    def get_next_data_for_downlink(self):
        return '\x00' * 1024

    def get_status_summary(self):
        return (1, ['array_voltage', 'battery_voltage'])


class FakeStatusGroup():
    def update(self):
        return

    def get_status(self):
        return


class TestPeers(BasicTestHarness):
    def setup(self):
        super(TestPeers, self).setup()
        # Set up port manually.
        config = self.basic_config.copy()
        config.Communicator.lowrate_link_parameters = [('comm1', ("localhost", 6501), 6501)]
        self.pyro_port = FAKE_PYRO_PORT
        peers = collections.OrderedDict([(k,('PYRO:communicator@localhost:%d' % (self.pyro_port + k))) for k in range(2)])
        self.c = camera_communicator.Communicator(cam_id=0, peers=peers, controller=None, pyro_port=self.pyro_port,
                                                  config=config)
        self.c.setup_pyro_daemon()
        self.c.start_pyro_thread()

        self.c.file_id = 0

        self.c.autosend_short_status_interval = 1e200 # disable autosending short status for these tests
        config.Communicator.lowrate_link_parameters = []
        self.peer = camera_communicator.Communicator(cam_id=1, peers={}, controller=None,
                                                     pyro_port=(self.pyro_port + 1),
                                                     config=config)
        self.peer.setup_pyro_daemon()
        self.peer.start_pyro_thread()

    def teardown(self):
        super(TestPeers, self).teardown()
        self.c.close()
        self.peer.close()

    @timed(20)
    def ping_peer_test(self):
        result = self.c.peers[1].ping()
        assert (result == True)

    @timed(20)
    def send_data_on_downlinks_test(self):
        self.c.peer_polling_order = [1] # This is manually set
        self.peer.controller = FakeController()
        print('Peers are:', self.c.peers)
        print('Peer polling order is:', self.c.peer_polling_order)
        self.hirate_downlink = FakeHirateDownlink()
        self.c.downlinks = dict(highrate=self.hirate_downlink)
        self.c.send_data_on_downlinks()
        print('%r' % self.hirate_downlink.queue[0])
        assert (self.hirate_downlink.queue == ('\x00' * 1024))
        self.c.send_short_status_periodically_via_highrate()

    @timed(20)
    def test_short_status(self):
        self.c.populate_short_status_leader()
        self.c.get_short_status_camera()

        status = self.c.get_next_status_summary()
        ss = short_status.ShortStatusLeader(status)
        status = self.c.get_next_status_summary()
        ss = short_status.ShortStatusCamera(status)
#        print ss.message_id
        assert ss.message_id == 0
        status = self.c.get_next_status_summary()
        ss = short_status.ShortStatusCamera(status)
        assert ss.message_id == 1
        status = self.c.get_next_status_summary()
        ss = short_status.ShortStatusLeader(status)
        status = self.c.get_next_status_summary()
        ss = short_status.ShortStatusCamera(status)
#        print ss.message_id
        assert ss.message_id == 0




