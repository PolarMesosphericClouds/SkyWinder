

import collections
import json
import logging
import os
import select
import threading
import time
import traceback

import Pyro4
import Pyro4.errors
import Pyro4.socketutil
import Pyro4.util
import numpy as np
from pymodbus.exceptions import ConnectionException
from traitlets import Int, Unicode, Bool, List, Float, Tuple, TCPAddress, Enum

from skywinder_streamlined_flight_control.communication import constants
from skywinder_streamlined_flight_control.communication import downlink_classes, packet_classes
#from skywinder_streamlined_flight_control.communication import file_format_classes
from skywinder_streamlined_flight_control.utils import error_counter, camera_id
from skywinder_streamlined_flight_control.utils.configuration import GlobalConfiguration

Pyro4.config.SERVERTYPE = "multiplex"
Pyro4.config.SERIALIZER = 'pickle'
Pyro4.config.SERIALIZERS_ACCEPTED = ['pickle', ]
# Caution: If COMMTIMEOUT is too low, camera communicator gets a timeout error when it requests data from another communicator.
Pyro4.config.COMMTIMEOUT = 5
# Tests show COMMTIMEOUT works.
# Note that there is another timeout POLLTIMEOUT
# "For the multiplexing server only: the timeout of the select or poll calls"

logger = logging.getLogger(__name__)

@Pyro4.expose
class Communicator(GlobalConfiguration):
    initial_peer_polling_order = List(trait=Int).tag(config=True)
    initial_leader_id = Int(default_value=0,min=0,max=7).tag(config=True)
    loop_interval = Float(default_value=0.01, allow_none=False, min=0).tag(config=True)
    lowrate_link_parameters = List(
        trait=Tuple(Enum(("comm1", "comm2", "openport")), TCPAddress(), Int(default_value=5001, min=1024, max=65535)),
        help='List of tuples - link name, lowrate downlink address and lowrate uplink port.'
             'e.g. [("comm1",("pmc-serial-1", 5001), 5001), ...]').tag(config=True)
    hirate_link_parameters = List(trait=Tuple(Enum(("openport", "highrate", "los")), TCPAddress(), Int(min=0)),
                                  help='List of tuples - hirate downlink name, Enum(("openport", "highrate", "los"))'
                                       'hirate downlink address,'
                                       'hirate downlink downlink speed in bytes per second. 0 means link is disabled.'
                                       'e.g. [("openport", ("192.168.1.70", 4501), 10000), ...]').tag(config=True)

    filewatcher_threshhold_time = Float(default_value=60, allow_none=False)

    def __init__(self, cam_id, peers, controller, pyro_port, **kwargs):
        super(Communicator, self).__init__(**kwargs)
        self.port = pyro_port
        logger.debug('Communicator initializing with config %r' % self.config)
        self.cam_id = cam_id
        self.leader_id = self.initial_leader_id
        self.become_leader = False
        self.battery_monitor = None
        self.file_id = 0
        self.lowrate_uplinks = []
        self.lowrate_downlinks = []
        self.downlinks = collections.OrderedDict()


        self.peers = collections.OrderedDict()
        for peer_id, peer in list(peers.items()):
            try:
                peer = Pyro4.Proxy(peer)
            except TypeError as e:
                if not hasattr(peer, '_pyroUri'):
                    if not hasattr(peer, 'cam_id'):
                        raise e
            self.peers[peer_id] = peer

        if controller:
            try:
                self.controller = Pyro4.Proxy(controller)
            except TypeError as e:
                if hasattr(controller, '_pyroUri') or hasattr(controller, 'pipeline'):
                    self.controller = controller
                else:
                    raise Exception("Invalid controller argument; must be URI string, URI object, or controller class")
        else:
            if self.use_controller:
                controller_uri = 'PYRO:controller@%s:%d' % ('0.0.0.0', self.controller_pyro_port)
                self.controller = Pyro4.Proxy(controller_uri)

        self.peer_polling_order_idx = 0
        self.peer_polling_order = self.initial_peer_polling_order

        self.short_status_order_idx = 0



        self.housekeeping = housekeeping_classes.construct_super_group_from_json_list(self.json_paths,
                                                                                      self.filewatcher_threshhold_time)

        self.sip_data_logger = SipDataLogger(sip_logging_dir=self.housekeeping_dir)

        self.end_loop = False

        self.pyro_daemon = None
        self.pyro_thread = None
        self.main_thread = None

        self.last_autosend_timestamp = 0

        self.command_logger = command_classes.CommandLogger()

        self.destination_lists = dict([(peer_id, [peer]) for (peer_id, peer) in list(self.peers.items())])
        self.destination_lists[command_table.DESTINATION_SUPER_COMMAND] = [self]
        self.destination_lists[command_table.DESTINATION_NARROWFIELD_CAMERAS] = [self.peers[index] for index in self.narrowfield_cameras]
        self.destination_lists[command_table.DESTINATION_WIDEFIELD_CAMERAS] = [self.peers[index] for index in self.widefield_cameras]
        self.destination_lists[command_table.DESTINATION_ALL_CAMERAS] = (self.destination_lists[command_table.DESTINATION_NARROWFIELD_CAMERAS]+
                                                                         self.destination_lists[command_table.DESTINATION_WIDEFIELD_CAMERAS])
        self.destination_lists[command_table.DESTINATION_LIDAR] = [self]  # The commands for the lidar are all brokered by the leader

        self.setup_links()

    @property
    def leader(self):
        return self.cam_id == self.leader_id

    def validate_command_table(self):
        """
        Ensure that all available commands defined in command_table are actually implemented by the communicator

        Raises
        -------
        AttributeError if a command in the table is not implemented
        """
        for command in command_manager.commands:
            try:
                function = getattr(self, command.name)
            except AttributeError:  # pragma: no cover
                raise AttributeError("Command %s is not implemented by communicator!" % command.name)  # pragma: no cover

    def close(self):
        self.end_loop = True
        time.sleep(0.01)
        if self.pyro_thread and self.pyro_thread.is_alive():
            self.pyro_thread.join(timeout=0)  # pragma: no cover
        if self.main_thread and self.main_thread.is_alive():
            self.main_thread.join(timeout=0)  # pragma: no cover
        try:
            self.pyro_daemon.shutdown()
        except Exception:
            logger.exception("Failure while shutting down pyro_daemon")
        try:
            for lowrate_uplink in self.lowrate_uplinks:
                lowrate_uplink.uplink_socket.close()
        except Exception:  # pragma: no cover
            logger.exception("Failure while closing uplink sockets")  # pragma: no cover
        logger.debug('Communicator deleted')

    def setup_pyro_daemon(self):
        self.pyro_daemon = Pyro4.Daemon(host='0.0.0.0', port=self.port)
        uri = self.pyro_daemon.register(self, "communicator")
        print(uri)

    def setup_links(self):
        self.file_id = 0
        self.lowrate_uplinks = []
        self.lowrate_downlinks = []
        self.downlinks = collections.OrderedDict()

        for lowrate_link_parameters in self.lowrate_link_parameters:
            self.lowrate_uplinks.append(uplink_classes.Uplink(lowrate_link_parameters[0], lowrate_link_parameters[2]))
            self.lowrate_downlinks.append(
                downlink_classes.LowrateDownlink(lowrate_link_parameters[0], *lowrate_link_parameters[1]))

        for name, (address, port), initial_rate in self.hirate_link_parameters:
            self.downlinks[name] = downlink_classes.HirateDownlink(ip=address, port=port,
                                                                   speed_bytes_per_sec=initial_rate, name=name)

    ### Loops to continually be run

    def start_main_thread(self):
        self.main_thread = threading.Thread(target=self.main_loop)
        self.main_thread.daemon = True
        logger.debug('Starting leader thread')
        self.main_thread.start()

    def main_loop(self):
        while not self.end_loop:
            self.get_and_process_sip_bytes()

            if self.leader:
                self.request_gps_info()
                self.send_short_status_periodically_via_highrate()
                self.send_data_on_downlinks()
                for charge_controller in self.charge_controllers:
                    try:
                        charge_controller.measure_and_log()
                    except ConnectionException:
                        logger.exception("Failed to connect to %s" % charge_controller.name)
                        getattr(self.error_counter, (charge_controller.name + '_connection_error')).increment()
            time.sleep(self.loop_interval)

    def start_pyro_thread(self):
        self.pyro_thread = threading.Thread(target=self.pyro_loop)
        self.pyro_thread.daemon = True
        logger.debug('Stating pyro thread')
        self.pyro_thread.start()

    def pyro_loop(self):
        while True:
            events, _, _ = select.select(self.pyro_daemon.sockets, [], [], 0.01)
            if events:
                self.pyro_daemon.events(events)
            if self.end_loop == True:
                return


    def send_data_on_downlinks(self):
        if not self.peers:
            raise RuntimeError(
                'Communicator has no peers. This should never happen; leader at minimum has self as peer.')  # pragma: no cover
        for link in list(self.downlinks.values()):
            if link.has_bandwidth():
                logger.debug('getting next data from camera %d' % peer_id)
                next_data = none
                active_peer = self.peers[peer_id]
                try:
                    if self.check_peer_connection(active_peer):
                        next_data = active_peer.get_next_data()  # pyro call
                except pyro4.errors.communicationerror as e:
                    active_peer_string = str(active_peer._pyrouri)
                    error_counter_key = 'pmc_%d_communication_error_counts' % peer_id
                    self.error_counter.counters[error_counter_key].increment()
                    logger.debug('connection to peer at uri %s failed. error counter - %r. error message: %s' % (
                        active_peer_string, self.error_counter.counters[error_counter_key], str(e)))
                except exception as e:
                    payload = str(e)
                    payload += "".join(pyro4.util.getpyrotraceback())
                    exception_file = file_format_classes.unhandledexceptionfile(payload=payload,
                                                                                request_id=file_format_classes.default_request_id,
                                                                                camera_id=peer_id)
                    next_data = exception_file.to_buffer()

                if not next_data:
                    logger.debug('no data was obtained.')
                else:
                    link.put_data_into_queue(next_data, self.file_id)
                    self.file_id += 1

                self.peer_polling_order_idx = (self.peer_polling_order_idx + 1) % len(self.peer_polling_order)

            else:
                if link.enabled:
                    link.send_data()

    ##### Methods called by leader via pyro

    def get_downlink_queue_depth(self):
        try:
            return self.controller.get_downlink_queue_depth()
        except Pyro4.errors.CommunicationError:
            self.error_counter.controller_communication_errors.increment()
            logger.debug('Connection to controller failed. Error counter - %r. Error message: %s' % (
                self.error_counter.controller_communication_errors, "".join(Pyro4.util.getPyroTraceback())))
        except Exception:
            raise Exception("".join(Pyro4.util.getPyroTraceback()))

    def get_next_data(self):
        try:
            logger.debug('Getting next data from controller.')
            return self.controller.get_next_data_for_downlink()
        except Pyro4.errors.CommunicationError:
            self.error_counter.controller_communication_errors.increment()
            logger.debug(
                'Connection to controller failed. Error counter - %r. Error message: %s' % (
                    self.error_counter.controller_communication_errors, "".join(Pyro4.util.getPyroTraceback())))
            return None
        except Exception as e:
            raise Exception(str(e) + "".join(Pyro4.util.getPyroTraceback()))

    def ping(self):
        return True

    def check_peer_connection(self, peer):
        initial_timeout = peer._pyroTimeout
        try:
            logger.debug("Pinging peer %r" % peer)
            peer._pyroTimeout = 0.1
            peer.ping()
            return True
        except Pyro4.errors.CommunicationError:
            details = "Ping failure for peer %s" % (peer._pyroUri)
            logger.warning(details)
            return False
        except Exception:
            logger.exception("Unexpected failure while checking connection to %r" % peer)
            return False
        finally:
            peer._pyroTimeout = initial_timeout
