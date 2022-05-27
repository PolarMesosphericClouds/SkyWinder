import struct
from nose.tools import assert_raises

from skywinder.communication.command_classes import (CommandLogger, CommandStatus, StringArgumentCommand,
                                                     ListArgumentCommand, Command)


class TestCommandLogger():
    def test_empty_command_logger(self):
        cl = CommandLogger()
        assert cl.get_highest_sequence_number_result() is None
        assert cl.get_latest_result() is None
        assert cl.total_commands_received == 0
        assert cl.sequence_numbers == []
        assert cl.get_highest_sequence_number_result() is None
        assert cl.get_last_sequence_skip() is None
        assert cl.get_last_failed_result() is None

    def test_last_sequence_skip(self):
        cl = CommandLogger()
        for seq in [0, 1, 2, 3, 8]:
            cl.add_command_result(seq, CommandStatus.command_ok, "")
        assert cl.get_last_sequence_skip() == 4
        for seq in [9, 10, 11]:
            cl.add_command_result(seq, CommandStatus.command_ok, "")
        assert cl.get_last_sequence_skip() == 4
        for seq in [12, 14, 15]:
            cl.add_command_result(seq, CommandStatus.command_ok, "")
        assert cl.get_last_sequence_skip() == 13

    def test_latest_result(self):
        cl = CommandLogger()
        cl.add_command_result(123, CommandStatus.command_ok, "details")
        timestamp, sequence, status, details = cl.get_latest_result()
        assert type(timestamp) is float
        assert sequence == 123
        assert status == CommandStatus.command_ok
        assert details == "details"

    def test_get_highest_sequence_number_result(self):
        cl = CommandLogger()
        cl.add_command_result(123, CommandStatus.command_error, "others")
        cl.add_command_result(128, CommandStatus.command_ok, "details")
        timestamp, sequence, status, details = cl.get_highest_sequence_number_result()
        assert type(timestamp) is float
        assert sequence == 128
        assert status == CommandStatus.command_ok
        assert details == "details"

    def test_get_last_failed_result(self):
        cl = CommandLogger()
        cl.add_command_result(122, CommandStatus.command_ok, "everything ok")
        assert cl.get_last_failed_result() is None
        cl.add_command_result(123, CommandStatus.command_error, "others")
        cl.add_command_result(128, CommandStatus.command_ok, "details")
        timestamp, sequence, status, details = cl.get_last_failed_result()
        assert type(timestamp) is float
        assert sequence == 123
        assert status == CommandStatus.command_error
        assert details == "others"


def test_bad_string_command():
    with assert_raises(ValueError):
        StringArgumentCommand("bad1", [('name', 'f')])

    with assert_raises(ValueError):
        StringArgumentCommand("bad1", [('a_string', 's'), ('name', 'f'), ('another_string', 's')])


def test_bad_string_encode():
    sac = StringArgumentCommand("command", [('the_string', 's')])
    sac._command_number = 33
    with assert_raises(ValueError):
        sac.encode_command()
    sac.encode_command(the_string='hello')


def test_bad_string_decode():
    sac = StringArgumentCommand("command", [('the_string', 's')])
    sac._command_number = 34
    encoded = sac.encode_command(the_string='hello there')
    kwargs, remainder = sac.decode_command_and_arguments(encoded)
    assert remainder == b''
    assert kwargs['the_string'] == b'hello there'
    assert len(kwargs) == 1
    with assert_raises(ValueError):
        sac.decode_command_and_arguments(encoded[:5])


def test_list_argument_decode_type():
    lac = ListArgumentCommand("set_peer_polling_order", 'B')
    lac._command_number = 35
    input_argument = list(range(10))
    encoded = lac.encode_command(input_argument)
    kwargs, remainder = lac.decode_command_and_arguments(encoded)
    assert remainder == b''
    list_argument = kwargs['list_argument']
    assert type(list_argument) is tuple
    assert list(list_argument) == input_argument


def test_truncated_list_argument_decode():
    lac = ListArgumentCommand("set_peer_polling_order", 'B')
    lac._command_number = 35
    encoded = lac.encode_command([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    with assert_raises(ValueError):
        lac.decode_command_and_arguments(encoded[:5])
    try:
        lac.decode_command_and_arguments(encoded[:5])
    except ValueError as e:
        print(e.message)


def test_bad_command_number_list_argument_decode():
    lac = ListArgumentCommand("set_peer_polling_order", 'B')
    lac._command_number = 35
    encoded = lac.encode_command([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    encoded = 'a' + encoded[1:]
    with assert_raises(ValueError):
        lac.decode_command_and_arguments(encoded)
    try:
        lac.decode_command_and_arguments(encoded)
    except ValueError as e:
        print(e.message)


def test_list_argument_loss_of_precision_encode():
    lac = ListArgumentCommand("set_peer_polling_order", 'B')
    lac._command_number = 35
    with assert_raises(struct.error):
        lac.encode_command([999, 1000])
    lac.encode_command([1.0, 2.1])


def test_generic_command_request_id_generator():
    cmd = Command("get_status_report", [("compress", "B"), ("request_id", 'I')])
    cmd._command_number = 27
    with assert_raises(ValueError):
        cmd.encode_command(compress=1)
    def request_id_generator():
        return 334
    cmd.set_request_id_generator(request_id_generator)
    encoded = cmd.encode_command(compress=1)
    kwargs,remainder = cmd.decode_command_and_arguments(encoded)
    assert kwargs['request_id'] == 334
    assert kwargs['compress'] == 1
    assert remainder == ''.encode('utf-8')

def test_generic_command_missing_parameter():
    cmd = Command("get_status_report", [("compress", "B"), ("request_id", 'I')])
    cmd._command_number = 27
    with assert_raises(ValueError):
        cmd.encode_command(request_id=33)

def test_generic_command_bad_decode():
    cmd = Command("get_status_report", [("compress", "B"), ("request_id", 'I')])
    cmd._command_number = 27
    encoded = cmd.encode_command(compress=1, request_id=33)
    encoded = 'a'.encode('utf-8')+encoded[1:]
    with assert_raises(ValueError):
        cmd.decode_command_and_arguments(encoded)

def test_generic_command_loss_of_precision():
    cmd = Command("get_status_report", [("compress", "B"), ("request_id", 'I')])
    cmd._command_number = 27
    encoded = cmd.encode_command(compress=1.01, request_id=33)
