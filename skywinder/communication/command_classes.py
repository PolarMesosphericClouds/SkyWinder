import logging
import struct
import time
from collections import OrderedDict

import numpy as np

import skywinder.utils.comparisons
from skywinder.communication.packet_classes import GSECommandPacket
from skywinder.utils.struct_formats import format_description

logger = logging.getLogger(__name__)

COMMAND_FORMAT_PREFIX = '>1B'


class Command(object):
    def __init__(self, name, argument_table, docstring = ''):
        self._name = name
        self._argument_table = argument_table
        self._argument_names = [argname for argname, format_ in self._argument_table]
        self._argument_name_to_format = dict(self._argument_table)
        self._command_format_prefix = COMMAND_FORMAT_PREFIX
        self._argument_format_string = ''.join([format_ for argname, format_ in self._argument_table])
        self._encoded_command_size_bytes = struct.calcsize(self._command_format_prefix + self._argument_format_string)
        self._command_number = None
        self._docstring=docstring
        self._request_id_generator = None

    @property
    def __doc__(self):
        return self.make_docstring()

    def set_request_id_generator(self,function):
        self._request_id_generator = function

    @property
    def argument_docs(self):
        argument_docs = 'Arguments:\n'
        for name,format_ in self._argument_table:
            description = format_description.get(format_,format_)
            argument_docs += '\t%s : %s\n' % (name,description)
        return argument_docs

    def make_docstring(self):
        return self._docstring + '\n' + self.argument_docs

    @property
    def name(self):
        return self._name

    @property
    def argument_table(self):
        return self._argument_table

    @property
    def command_number(self):
        return self._command_number

    @property
    def encoded_command_size_bytes(self):
        return self._encoded_command_size_bytes

    @property
    def command_format_string(self):
        return self._command_format_prefix + self._argument_format_string

    def decode_command_and_arguments(self, data):
        if len(data) < self.encoded_command_size_bytes:
            raise ValueError(("Data string %r has length %d, which is not long enough for length %d of "
                              "command %s") % (data, len(data), self.encoded_command_size_bytes, self.name))
        values = struct.unpack(self.command_format_string, data[:self.encoded_command_size_bytes])
        remainder = data[self.encoded_command_size_bytes:]
        command_number = values[0]
        values = values[1:]
        if command_number != self.command_number:
            raise ValueError("Received command number %d which does not correspond to %d for command %s"
                             % (command_number, self.command_number, self.name))
        kwargs = dict(list(zip(self._argument_names, values)))
        return kwargs, remainder

    def encode_command(self, **kwargs):
        values = [self._command_number]
        if 'request_id' in self._argument_names:
            if 'request_id' not in kwargs:
                if self._request_id_generator:
                    kwargs['request_id'] = self._request_id_generator()
                else:
                    raise ValueError("request_id not specified for %s and no request_id generator has been set." % (self.name))
        for key in kwargs:
            if key not in self._argument_names:
                raise ValueError("Command %s does not take argument '%s'" % (self.name, key))
        for argument_name in self._argument_names:
            if not argument_name in kwargs:
                raise ValueError("Parameter %s missing when encoding %s" % (argument_name, self.name))
            format_ = self._argument_name_to_format[argument_name]
            value = kwargs[argument_name]
            formatted_value, = struct.unpack('>' + format_, struct.pack('>' + format_, value))
            if not skywinder.utils.comparisons.equal_or_close(value, formatted_value):
                logger.critical("Formatting parameter %s as '%s' results in loss of information!\nOriginal value "
                                "%r   Formatted value %r" % (argument_name, format_, value, formatted_value))
            values.append(value)
        encoded_command = struct.pack(self._command_format_prefix + self._argument_format_string, *values)
        return encoded_command

    def __call__(self, **kwargs):
        return self.encode_command(**kwargs)


class ListArgumentCommand(Command):
    def __init__(self, name, argument_format, docstring=''):
        super(ListArgumentCommand, self).__init__(name, [('number', 'B')],docstring=docstring)
        self._argument_format = argument_format
    @property
    def __doc__(self):
        return self.make_docstring()

    @property
    def argument_docs(self):
        argument_docs = 'Argument:\nList of %s' % format_description.get(self._argument_format,self._argument_format)
        return argument_docs

    def decode_command_and_arguments(self, data):
        length_dict, _ = super(ListArgumentCommand, self).decode_command_and_arguments(data)
        num_arguments = length_dict['number']
        full_format_string = self._command_format_prefix + self._argument_format_string + self._argument_format * num_arguments
        total_length = struct.calcsize(full_format_string)
        if len(data) < total_length:
            raise ValueError(("Received command string has length %d which is not long enough. %d bytes needed for %d "
                              "arguments encoded as %s") % (
                             len(data), total_length, num_arguments, self._argument_format))
        values = struct.unpack(full_format_string, data[:total_length])
        remainder = data[total_length:]
        command_number = values[0]
        num_arguments = values[1]
        kwargs = dict(list_argument=values[2:])
        if command_number != self.command_number:
            raise ValueError("Received command number %d which does not correspond to %d for command %s"
                             % (command_number, self.command_number, self.name))
        return kwargs, remainder

    def encode_command(self, list_argument):
        number = len(list_argument)
        start_of_encoded_command = super(ListArgumentCommand, self).encode_command(number=number)

        for value in list_argument:
            formatted_value, = struct.unpack('>' + self._argument_format,
                                             struct.pack('>' + self._argument_format, value))
            if not skywinder.utils.comparisons.equal_or_close(value, formatted_value):
                logger.critical("Formatting parameter '%s' results in loss of information!\nOriginal value "
                                "%r   Formatted value %r" % (self._argument_format, value, formatted_value))
        encoded_list = struct.pack(('>' + self._argument_format * number), *list_argument)
        return start_of_encoded_command + encoded_list

    def __call__(self, list_argument):
        return self.encode_command(list_argument)


class StringArgumentCommand(Command):
    def __init__(self, name, argument_table, docstring=''):
        self.validate_argument_table(argument_table)
        argument_subtable = argument_table[:-1]
        argument_subtable.append(('string_length', 'B'))
        self._string_argument_name = argument_table[-1][0]
        super(StringArgumentCommand, self).__init__(name, argument_subtable, docstring=docstring)
    @property
    def __doc__(self):
        return self.make_docstring()

    @property
    def argument_docs(self):
        argument_docs = 'Arguments:\n'
        for name,format_ in self._argument_table:
            if name == 'string_length':
                continue
            description = format_description.get(format_,format_)
            argument_docs += '\t%s : %s\n' % (name,description)
        argument_docs += '\t%s : %s\n' % (self._string_argument_name, "string")
        return argument_docs


    def validate_argument_table(self, argument_table):
        last_argument_name, last_argument_format = argument_table[-1]
        if last_argument_format != 's':
            raise ValueError("Last argument of a StringArgumentCommand must have type specifier 's'")
        for index, (name, format_) in enumerate(argument_table):
            if index == len(argument_table) - 1:
                if format_ != 's':
                    raise ValueError("Last argument of a StringArgumentCommand must have type specifier 's'") # pragma: no cover
            else:
                if format_ == 's':
                    raise ValueError("Only one argument can have type specifier 's'")

    def decode_command_and_arguments(self, data):
        kwargs, remainder = super(StringArgumentCommand, self).decode_command_and_arguments(data)
        string_length = kwargs.pop('string_length')
        if len(remainder) < string_length:
            raise ValueError(("Received command string has length %d which is not long enough for "
                              "string of length %d") % (len(data), string_length))
        kwargs[self._string_argument_name] = remainder[:string_length]
        remainder = remainder[string_length:]
        return kwargs, remainder

    def encode_command(self, **kwargs):
        try:
            string_argument = kwargs.pop(self._string_argument_name)
        except KeyError:
            raise ValueError("Argument %s was not specified" % self._string_argument_name)
        kwargs['string_length'] = len(string_argument)
        start_of_encoded_command = super(StringArgumentCommand, self).encode_command(**kwargs)
        return start_of_encoded_command + string_argument


class CommandLogger(object):
    def __init__(self):
        self.command_history = []

    def add_command_result(self, sequence_number, status, details):
        timestamp = time.time()
        self.command_history.append((timestamp, sequence_number, status, details))

    def get_latest_result(self):
        if not self.command_history:
            return None
        return self.command_history[-1]

    @property
    def total_commands_received(self):
        return len(self.command_history)

    @property
    def sequence_numbers(self):
        return [sequence_number for _, sequence_number, _, _ in self.command_history]

    def get_highest_sequence_number_result(self):
        if not self.command_history:
            return None
        index = np.argmax(self.sequence_numbers)
        return self.command_history[index]

    def get_last_sequence_skip(self):
        sequence = self.sequence_numbers
        sequence.sort()
        diff = np.diff(sequence)
        indexes = np.flatnonzero(diff!=1)
        if len(indexes):
            return sequence[indexes[-1]]+1  # plus one makes this equal to the sequence number that we expected but are missing
        else:
            return None

    def get_last_failed_result(self):
        failures = [result for result in self.command_history if result[2] != CommandStatus.command_ok]
        if not failures:
            return None
        return failures[-1]


class CommandManager(object):
    def __init__(self):
        self._command_dict = OrderedDict()
        self._next_command_number = 0

    def add_command(self, command):
        if self._next_command_number == 255:
            # pragma: no cover
            raise RuntimeError("The total number of commands has exceeded 255. "
                               "Either some commands need to be removed/optimized or the command number needs to be "
                               "promoted to 2 bytes.")  # pragma: no cover
        command._command_number = self._next_command_number
        self._command_dict[command._command_number] = command
        setattr(self, command.name, command)
        self._next_command_number += 1

    def __getitem__(self, item):
        return self._command_dict[item]

    def get_command_by_name(self, name):
        for command in list(self._command_dict.values()):
            if command.name == name:
                return command

    @property
    def commands(self):
        return list(self._command_dict.values())

    @property
    def total_commands(self):
        return self._next_command_number

    def decode_commands(self, data):
        remainder = data
        commands = []
        while remainder:
            if remainder[0] == GSECommandPacket.COMMAND_PAD_BYTE:
                remainder = remainder[1:]
                continue
            command_number, = struct.unpack(COMMAND_FORMAT_PREFIX, remainder[:1])
            command = self[command_number]
            kwargs, remainder = command.decode_command_and_arguments(remainder)
            commands.append((command.name, kwargs))
        return commands


class CommandStatus():
    command_ok = 0
    failed_to_ping_destination = 1
    command_error = 2
