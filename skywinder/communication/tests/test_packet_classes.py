from nose.tools import assert_raises

from skywinder.communication import packet_classes


def test_gse_short_packet_roundtrip():
    packet = packet_classes.GSEPacket(sync2_byte=0xFA, origin=1, payload='hi there!')
    packet2 = packet_classes.GSEPacket(buffer=packet.to_buffer())
    assert packet.sync2_byte == packet2.sync2_byte
    assert packet.origin == packet2.origin
    assert packet.payload_length == packet2.payload_length
    assert packet.checksum == packet2.checksum
    assert packet.payload == packet2.payload

def test_gse_long_packet_roundtrip():
    packet = packet_classes.GSEPacket(sync2_byte=0xFA, origin=1, payload='hi there!' * 300)
    packet2 = packet_classes.GSEPacket(buffer=packet.to_buffer())
    assert packet.sync2_byte == packet2.sync2_byte
    assert packet.origin == packet2.origin
    assert packet.payload_length == packet2.payload_length
    assert packet.checksum == packet2.checksum
    assert packet.payload == packet2.payload

def test_gse_packet_missing_checksum_index_error():
    buffer = packet_classes.GSEPacket(sync2_byte=0xFA, origin=1, payload='hi there!' * 300).to_buffer()
    with assert_raises(packet_classes.PacketInsufficientLengthError):
        packet_classes.GSEPacket(buffer=buffer[:-1])

def test_invalid_gse_packet_params():
    # bad sync2 byte
    with assert_raises(ValueError):
        packet = packet_classes.GSEPacket(sync2_byte=12, origin=1, payload='hi there')

    #bad origin byte
    with assert_raises(ValueError):
        packet = packet_classes.GSEPacket(sync2_byte=0xFA, origin=1023, payload='hi there')

def test_insufficient_init_args():
    with assert_raises(ValueError):
        messed_up_packet = packet_classes.GSEPacket(payload='hi there!')

def test_gse_repr_doesnt_fail():
    messed_up_packet = packet_classes.GSEPacket(sync2_byte=0xFA, origin=1, payload='hi there!')
    messed_up_packet.sync2_byte = None
    messed_up_packet.origin = None
    messed_up_packet.__repr__()

    messed_up_packet = packet_classes.GSEPacket(sync2_byte=0xFA, origin=1, payload='hi there!')
    messed_up_packet.payload = None
    messed_up_packet.sync2_byte = None
    messed_up_packet.origin = None
    messed_up_packet.__repr__()

def test_long_hirate_packet():
    with assert_raises(ValueError):
        packet = packet_classes.FilePacket(file_id=12, packet_number=1, total_packet_number=8,
                                           payload='a'*(packet_classes.FilePacket._max_payload_size + 1))

def test_invalid_packet_number():
    with assert_raises(ValueError):
        packet = packet_classes.FilePacket(file_id=12, packet_number=10, total_packet_number=3, payload='hello')

def test_invalid_start_byte():
    packet = packet_classes.GSEPacket(sync2_byte=0xFA, origin=1, payload='hi there!')
    buffer = packet.to_buffer()
    buffer = '\x23' + buffer[1:]
    with assert_raises(packet_classes.PacketValidityError):
        _ = packet_classes.GSEPacket(buffer=buffer)
def test_hirate_packet_roundtrip():
    packet = packet_classes.FilePacket(file_id=99, packet_number=1, total_packet_number=10,
                                       payload="the payload is long")
    packet2 = packet_classes.FilePacket(buffer=packet.to_buffer())
    assert packet.file_id == packet2.file_id
    assert packet.payload_crc == packet2.payload_crc
    assert packet.payload_length == packet2.payload_length
    assert packet.payload == packet2.payload
    assert packet.packet_number == packet2.packet_number
    assert packet.total_packet_number == packet2.total_packet_number

def test_gse_acknowledgements():
    for ack in [0x00, 0x0A, 0x0B, 0x0C, 0x0D]:
        assert ack == packet_classes.decode_gse_acknowledgement(packet_classes.encode_gse_acknowledgement(ack))[0]
    valid = packet_classes.encode_gse_acknowledgement(0x00)
    for index in range(3):
        bytes = list(valid)
        bytes[index] = 'a'
        with assert_raises(packet_classes.PacketValidityError):
            packet_classes.decode_gse_acknowledgement(''.join(bytes))

def test_gse_command_packet_max_payload_length():
    with assert_raises(ValueError):
        packet = packet_classes.GSECommandPacket(payload=('a'*255), sequence_number=456, destination=0,
                                                 link_tuple=packet_classes.GSECommandPacket.TDRSS1)


def test_gse_command_packet_min_payload_length():
    packet = packet_classes.GSECommandPacket(payload=('a'), sequence_number=456, destination=0,
                                             link_tuple=packet_classes.GSECommandPacket.TDRSS1)
    assert len(packet.payload) >= packet_classes.GSECommandPacket._minimum_payload_length


def test_packet_from_buffer():
    packet = packet_classes.GSEPacket(sync2_byte=0xFA, origin=1, payload='hi there!' * 30)
    buffer = packet.to_buffer()
    packets,remainder = packet_classes.get_packets_from_buffer(buffer,packet_classes.GSEPacket,packet_classes.GSEPacket.START_BYTE)
    packet2 = packets[0]
    assert remainder == ''
    assert packet.sync2_byte == packet2.sync2_byte
    assert packet.origin == packet2.origin
    assert packet.payload_length == packet2.payload_length
    assert packet.checksum == packet2.checksum
    assert packet.payload == packet2.payload

    packets,remainder = packet_classes.get_packets_from_buffer(buffer[:30],packet_classes.GSEPacket,packet_classes.GSEPacket.START_BYTE)
    assert packets == []
    assert remainder == buffer[:30]

    buffer2 = buffer + chr(packet_classes.GSEPacket.START_BYTE)
    packets,remainder = packet_classes.get_packets_from_buffer(buffer2,packet_classes.GSEPacket,packet_classes.GSEPacket.START_BYTE)
    packet2 = packets[0]
    assert remainder == chr(packet_classes.GSEPacket.START_BYTE)
    assert packet.sync2_byte == packet2.sync2_byte
    assert packet.origin == packet2.origin
    assert packet.payload_length == packet2.payload_length
    assert packet.checksum == packet2.checksum
    assert packet.payload == packet2.payload

    buffer3 = buffer + 'asdb' + buffer2
    packets,remainder = packet_classes.get_packets_from_buffer(buffer3,packet_classes.GSEPacket,packet_classes.GSEPacket.START_BYTE)
    assert remainder == chr(packet_classes.GSEPacket.START_BYTE)
    assert len(packets) == 2
    for packet2 in packets:
        assert packet.sync2_byte == packet2.sync2_byte
        assert packet.origin == packet2.origin
        assert packet.payload_length == packet2.payload_length
        assert packet.checksum == packet2.checksum
        assert packet.payload == packet2.payload

    buffer3 = buffer + buffer[:30] + buffer*20
    packets,remainder = packet_classes.get_packets_from_buffer(buffer3,packet_classes.GSEPacket,packet_classes.GSEPacket.START_BYTE)
    print(repr(remainder))
    assert remainder == ''
    assert len(packets) == 21
    for packet2 in packets:
        assert packet.sync2_byte == packet2.sync2_byte
        assert packet.origin == packet2.origin
        assert packet.payload_length == packet2.payload_length
        assert packet.checksum == packet2.checksum
        assert packet.payload == packet2.payload
