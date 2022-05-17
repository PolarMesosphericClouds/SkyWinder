from nose.tools import timed, assert_raises, assert_is_not_none
from pmc_turbo.communication.command_classes import ListArgumentCommand,StringArgumentCommand
from pmc_turbo.communication.command_table import command_manager, destination_to_string

from pmc_turbo.communication.packet_classes import GSECommandPacket

def test_destination_to_string():
    for destination in range(10):
        assert_is_not_none(destination_to_string(destination))

def test_list_argument_command_round_trip():
    c = ListArgumentCommand("some_command",'1H')
    c._command_number=45

    list_argument = list(range(10))
    encoded = c.encode_command(list_argument)
    kwargs,remainder = c.decode_command_and_arguments(encoded)
    for a,b in  zip(kwargs['list_argument'],list_argument):
        assert a==b

def test_string_argument_command_round_trip():
    c = StringArgumentCommand("request_specific_file", [("max_num_bytes",'1i'), ("request_id",'1I'),
                                                                            ("filename", "s")])
    c._command_number = 46

    filename='/home/data/file.txt'
    request_id = 245333
    max_num_bytes=-453
    encoded = c.encode_command(filename=filename,request_id=request_id,max_num_bytes=max_num_bytes)
    kwargs,remainder = c.decode_command_and_arguments(encoded)
    assert kwargs['filename'] == filename
    assert kwargs['request_id'] == request_id
    assert kwargs['max_num_bytes'] == max_num_bytes

@timed(1)
def test_multiple_command_decoding():
    p1 = command_manager.get_command_by_name('set_focus')(focus_step=4900)
    p2 = command_manager.get_command_by_name('set_peer_polling_order')([1,2,3,4,5,6])
    result = command_manager.decode_commands(p1+p2+p1+p2+p1+p1+p2+p2)

def test_command_padding_gets_stripped():
    p1 = command_manager.get_command_by_name('set_focus')(focus_step=0xFFFF)
    result = command_manager.decode_commands(p1 + GSECommandPacket.COMMAND_PAD_BYTE*8)
    assert result[0][0]=='set_focus'
    assert len(result) == 1
    result = command_manager.decode_commands(GSECommandPacket.COMMAND_PAD_BYTE*8 + p1 + GSECommandPacket.COMMAND_PAD_BYTE*8)
    assert result[0][0]=='set_focus'
    assert len(result) == 1

def test_doc():
    for command in command_manager.commands:
        assert type(command.__doc__) is str
        assert command.argument_table == command._argument_table

def test_short_command():
    with assert_raises(ValueError):
        command_manager.commands[0].decode_command_and_arguments('')

def test_bad_arg():
    with assert_raises(ValueError):
        command_manager.commands[0].encode_command(blargh=55)
        command_manager.commands[0].encode_command()