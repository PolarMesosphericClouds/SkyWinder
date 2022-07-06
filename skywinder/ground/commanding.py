import os
import socket
import logging

import serial
import time

import sys
from traitlets.config import Application
from traitlets import Float, Unicode, List, Enum

import skywinder.utils.configuration
from skywinder.communication.command_table import command_manager

from skywinder.communication.packet_classes import (CommandPacket,
                                                    GSECommandPacket,
                                                    PacketError,
                                                    decode_gse_acknowledgement,
                                                    gse_acknowledgment_codes,
                                                    gse_acknowledgment_length)
from skywinder.ground.ground_configuration import GroundConfiguration
from skywinder.communication.command_table import DESTINATION_SUPER_COMMAND

logger = logging.getLogger(__name__)

LOS1 = GSECommandPacket.LOS1
LOS2 = GSECommandPacket.LOS2
TDRSS1 = GSECommandPacket.TDRSS1
TDRSS2 = GSECommandPacket.TDRSS2
IRIDIUM1 = GSECommandPacket.IRIDIUM1
IRIDIUM2 = GSECommandPacket.IRIDIUM2

OPENPORT = 'openport'
link_ids = {LOS1: 'los1', LOS2: 'los2',
            TDRSS1: 'tdrss1', TDRSS2: 'tdrss2',
            IRIDIUM1: 'iridium1', IRIDIUM2: 'iridium2',
            OPENPORT: 'openport'}
link_name_to_id = dict([(v,k) for (k,v) in list(link_ids.items())])

class CommandHistoryLogger(GroundConfiguration):
    column_names = ['send_timestamp', 'sequence_number', 'num_commands', 'destination',
                    'link_id', 'acknowledgement_code', 'send_successful', 'command_blob_file']

    def __init__(self, **kwargs):
        super(CommandHistoryLogger, self).__init__(**kwargs)
        timestring = time.strftime('%Y-%m-%d_%H%M%S')
        self.command_history_path = os.path.join(self.root_data_path, self.command_history_subdir, timestring)
        os.makedirs(self.command_history_path)
        self.command_history_index_filename = os.path.join(self.command_history_path,'index.csv')
        self.create_command_history_index_file()

    def create_command_history_index_file(self):
        with open(self.command_history_index_filename, 'w') as fh:
            fh.write(','.join(self.column_names) + '\n')

    def write_row(self, send_timestamp, sequence_number, num_commands, destination, link_id, acknowledgement_code,
                  send_successful, command_blob):
        command_blob_file = self.write_command_blob(send_timestamp, sequence_number, command_blob)
        with open(self.command_history_index_filename, 'a') as fh:
            fh.write(
                ','.join([str(x) for x in (send_timestamp, sequence_number, num_commands, destination, link_id, acknowledgement_code,
                          send_successful, command_blob_file)]) + '\n')

    def write_command_blob(self, timestamp, sequence_number, command_blob):
        timestring = time.strftime('%Y-%m-%d_%H%M%S', time.localtime(timestamp))
        filename = os.path.join(self.command_history_path, ('%s_%05d' % (timestring, sequence_number)))
        with open(filename, 'w') as fh:
            fh.write(command_blob)
        return filename


class CommandSender(GroundConfiguration):
    command_port_baudrate = 2400  # LDB 2.1.2
    command_port_response_timeout = Float(3., help="Timeout for serial command port. This sets how much time is "
                                                   "allocated for the GSE to acknowledge the command we sent.",
                                          min=0).tag(config=True)

    def __init__(self, **kwargs):
        super(CommandSender, self).__init__(**kwargs)

        self.command_manager = command_manager
        self.openport_link = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.openport_link.bind(self.openport_origin_address)
        if self.command_port:
            self.serial_port = serial.Serial(self.command_port, baudrate=self.command_port_baudrate,
                                             timeout=self.command_port_response_timeout)
        else:
            self.serial_port = None
        self._current_link_id = OPENPORT
        self.history_logger = CommandHistoryLogger(**kwargs)
        self.sequence_number_filename = os.path.join(self.root_data_path, 'next_command_sequence_number')
        self.request_id_filename = os.path.join(self.root_data_path, 'next_request_id')
        self.current_link_filename = os.path.join(self.root_data_path, 'current_link')
        try:
            with open(self.sequence_number_filename) as fh:
                self.next_sequence_number = int(fh.read())
                logger.info("Read next command sequence number %d from disk" % self.next_sequence_number)
        except Exception as e:
            logger.exception("Could not read next command sequence number from disk, starting at zero")
            self.next_sequence_number = 0
        try:
            with open(self.request_id_filename) as fh:
                self.next_request_id = int(fh.read())
                logger.info("Read next request_id %d from disk" % self.next_request_id)
        except Exception as e:
            logger.exception("Could not read next request_id from disk, starting at zero")
            self.next_request_id = 0

        for command in list(command_manager._command_dict.values()):
            setattr(self, command.name, command)
            command.set_request_id_generator(self._get_next_request_id)

    @property
    def current_link_id(self):
        self._read_current_link_from_disk()
        return self._current_link_id

    @property
    def current_link(self):
        return link_ids[self.current_link_id]

    def _read_current_link_from_disk(self):
        try:
            with open(self.current_link_filename) as fh:
                link_from_file = fh.read()
                try:
                    self._current_link_id = link_name_to_id[link_from_file]
                    logger.info("Read link %r from disk" % (link_ids[self._current_link_id]))
                except KeyError:
                    logger.error("Found unknown link name %r in current link file %r, reverting to default link" %
                                 (link_from_file,self.current_link_filename))
        except Exception as e:
            logger.exception("Could not read current link from disk, using default link %r" %
                             (link_ids[self._current_link_id]))

    def _write_current_link_to_disk(self):
        try:
            with open(self.current_link_filename,'w') as fh:
                fh.write(link_ids[self._current_link_id])
                logger.info("Wrote current link %r to disk" % link_ids[self._current_link_id])
            os.chmod(self.current_link_filename,0o777)
        except Exception:
            logger.exception("Failed to write current link to file %r" % self.current_link_filename)


    def _get_next_request_id(self):
        next = self.next_request_id
        message = ("Using request_id %d" % next)
        logger.info(message)
        print(message)
        self.next_request_id += 1
        try:
            with open(self.request_id_filename, 'w') as fh:
                fh.write('%d' % self.next_request_id)
                logger.debug("Next request_id %d written to disk" % self.next_request_id)
            os.chmod(self.request_id_filename,0o777)
        except Exception:
            logger.exception("Could not write next request_id %d to disk" % self.next_request_id)

        return next

    def set_link_openport(self):
        self._current_link_id = OPENPORT
        self._write_current_link_to_disk()

    def set_link_los1(self):
        self._current_link_id = LOS1
        self._write_current_link_to_disk()

    def set_link_los2(self):
        self._current_link_id = LOS2
        self._write_current_link_to_disk()

    def set_link_tdrss1(self):
        self._current_link_id = TDRSS1
        self._write_current_link_to_disk()

    def set_link_tdrss2(self):
        self._current_link_id = TDRSS2
        self._write_current_link_to_disk()

    def set_link_iridium1(self):
        self._current_link_id = IRIDIUM1
        self._write_current_link_to_disk()

    def set_link_iridium2(self):
        self._current_link_id = IRIDIUM2
        self._write_current_link_to_disk()

    def send(self, payload, destination, via=None):
        """
        Send command payload to a destination system

        Parameters
        ----------
        payload
        destination: camera (0-7), or special DESTINATION_... constant defined in skywinder.communication.command_table
        via: a link_id, default is None, meaning use current link

        Possible destinations:
         - DESTINATION_ALL_CAMERAS
         - DESTINATION_WIDEFIELD_CAMERAS
         - DESTINATION_NARROWFIELD_CAMERAS
         - DESTINATION_LIDAR
         - DESTINATION_SUPER_COMMAND

        """
        commands = command_manager.decode_commands(payload)
        result = None
        if via is None:
            via = self.current_link_id

        message = ''
        if via == OPENPORT:
            if destination == DESTINATION_SUPER_COMMAND:
                logger.warning("Sending super command via open port might not reach all cameras. "
                               "The command will be sent, but cannot be guaranteed to reach all cameras.")
            packet = CommandPacket(payload=payload, sequence_number=self.next_sequence_number, destination=destination)
            command_blob = packet.to_buffer()
            timestamp = time.time()
            try:
                for address in self.openport_uplink_addresses:
                    self.openport_link.sendto(command_blob, address)
                acknowledgement_code = 0x00
                send_successful = 1
            except socket.error:
                logger.exception("Failed to send command sequence number %d" % self.next_sequence_number)
                acknowledgement_code = 0xFF
                send_successful = 0


        elif via in [LOS1, LOS2, TDRSS1, TDRSS2, IRIDIUM1, IRIDIUM2]:
            packet = GSECommandPacket(payload=payload, sequence_number=self.next_sequence_number,
                                      destination=destination,
                                      link_tuple=via)
            command_blob = packet.to_buffer()
            timestamp = time.time()
            self.serial_port.write(command_blob)
            response = self.serial_port.read(gse_acknowledgment_length)
            if response != '':
                try:
                    acknowledgement_code, remainder = decode_gse_acknowledgement(response)
                    if acknowledgement_code == 0x00:
                        send_successful = 1
                    else:
                        send_successful = 0
                except PacketError:
                    logger.exception("Failed to decode GSE response %r to command sequence number %d" %( response, self.next_sequence_number))
                    acknowledgement_code = 0xFF
                    send_successful = 0
            else:
                message = "No response received from GSE!"
                acknowledgement_code = 0xFF
                send_successful = 0
        else:
            raise ValueError("Unknown uplink specified %r" % via)

        if not message:
            message = gse_acknowledgment_codes.get(acknowledgement_code,'Unknown exception occurred while sending or decoding GSE response')
        if send_successful:
            message = ("Successfully sent command sequence %d via %s with destination %d"
                        % (self.next_sequence_number, link_ids[via], destination))
            logger.info(message)
            print(time.ctime() + " : " + message)
        else:
            message = ("Failed to send command sequence %d via %s!\n\tMessage: %s"
                             % (self.next_sequence_number, link_ids[via], message))
            logger.error(message)
            print(message)

        self.history_logger.write_row(send_timestamp=timestamp, sequence_number=self.next_sequence_number,
                                      num_commands=len(commands), destination=destination, link_id=link_ids[via],
                                      acknowledgement_code=acknowledgement_code, send_successful=send_successful,
                                      command_blob=command_blob)
        self.next_sequence_number += 1
        try:
            with open(self.sequence_number_filename, 'w') as fh:
                fh.write('%d' % self.next_sequence_number)
                logger.debug("Next command sequence number %d written to disk" % self.next_sequence_number)
            os.chmod(self.sequence_number_filename,0o777)
        except Exception:
            logger.exception("Could not write next command sequence number %d to disk" % self.next_sequence_number)
        return result


class CommandSenderApp(Application):
    config_file = Unicode('', help="Load this config file").tag(config=True)
    config_dir = Unicode(skywinder.utils.configuration.default_ground_config_dir, help="Config file directory").tag(config=True)
    write_default_config = Unicode('', help="Write template config file to this location").tag(config=True)
    classes = List([CommandSender])
    mode = Enum(['full', 'piggyback', 'piggyback_sim', 'no_serial_connections', 'palestine'],default_value='full', help="configuration shortcut to setup for piggyback or full system").tag(config=True)
    aliases = dict(generate_config='CommandSenderApp.write_default_config',
                   config_file='CommandSenderApp.config_file',
                   mode='CommandSenderApp.mode')

    def initialize(self, argv=None):
        actual_argv = argv
        if argv is None:
            actual_argv = sys.argv
        print("initializing CommandSender with arguments:",actual_argv)
        self.parse_command_line(argv)
        if self.write_default_config:
            with open(self.write_default_config, 'w') as fh:
                fh.write(self.generate_config_file())
                self.exit()
        if self.config_file:
            print("**** Ignoring any --mode option ****")
        else:
            if self.mode == 'full':
                print("Using full configuration mode")
                self.config_file = 'default_ground_config.py'
            elif self.mode == 'piggyback':
                print("Using piggyback configuration mode")
                self.config_file = 'piggyback_ground_config.py'
            elif self.mode == 'piggyback_sim':
                print("Using piggyback simulator configuration mode")
                self.config_file = 'simulated_piggyback_ground_config.py'
            elif self.mode == 'no_serial_connections':
                print('Using no serial connection configuration mode')
                self.config_file = 'no_serial_connection_config.py'
            elif self.mode == 'palestine':
                print('Using palestine configuration mode')
                self.config_file = 'palestine_config.py'
            else:
                raise RuntimeError("Unexpected usage: either specify --config_file or use a valid --mode option")
        print('loading config: ', self.config_dir, self.config_file)
        self.load_config_file(self.config_file, path=self.config_dir)

        print(self.config)
        self.command_sender = CommandSender(config=self.config)
