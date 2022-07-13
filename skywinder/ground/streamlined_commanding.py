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


class CommandSender():
    command_port_baudrate = 2400  # LDB 2.1.2
    command_port_response_timeout = 3.0

    def __init__(self, command_port=None, baudrate=2400, timeout=3.0):
        super(CommandSender, self).__init__(**kwargs)

        self.command_manager = command_manager
        if command_port:
            self.serial_port = serial.Serial(self.command_port, baudrate=baudrate,
                                             timeout=timeout)
        else:
            self.serial_port = None
        self._current_link_id = TDRSS1
        self.next_sequence_number = 0

        for command in list(command_manager._command_dict.values()):
            setattr(self, command.name, command)

    def set_link_openport(self):
        self._current_link_id = OPENPORT

    def set_link_los1(self):
        self._current_link_id = LOS1

    def set_link_los2(self):
        self._current_link_id = LOS2

    def set_link_tdrss1(self):
        self._current_link_id = TDRSS1

    def set_link_tdrss2(self):
        self._current_link_id = TDRSS2

    def set_link_iridium1(self):
        self._current_link_id = IRIDIUM1

    def set_link_iridium2(self):
        self._current_link_id = IRIDIUM2

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
        result = None
        if via is None:
            via = self._current_link_id

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

        return result
