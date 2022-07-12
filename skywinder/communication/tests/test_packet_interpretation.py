import unittest
import numpy as np
from skywinder.communication import packet_classes, file_format_classes


class test_sip_packet_malfunctions(unittest.TestCase):
    def test_empty_packet(self):
        buffer = b'\xfa\xff\x01\x00\x00\x00\x01'
        packets, remainder = packet_classes.get_packets_from_buffer(buffer,
                                                                    packet_class=packet_classes.GSEPacket,
                                                                    start_byte=packet_classes.GSEPacket.START_BYTE)
        assert (remainder == b'')
        assert (packets[0].to_buffer() == buffer)



    def test_sip_packet_in_data(self):
        initial_buffer = b'\xfa\xff\x01\x00\x00\x00\x01'
        np.random.seed(0)
        random_msg = np.random.randint(0, 255, size=10000).astype('uint8').tobytes()
        buffer = random_msg[:(len(random_msg) // 2)] + initial_buffer + random_msg[(len(random_msg) // 2):]
        packets, remainder = packet_classes.get_packets_from_buffer(buffer,
                                                                    packet_class=packet_classes.GSEPacket,
                                                                    start_byte=packet_classes.GSEPacket.START_BYTE)


        assert (packets[0].to_buffer() == initial_buffer)

    def test_false_start(self):
        buffer = b'\xfa\xfa\xff\x01\x00\x00\x00\x01'
        packets, remainder = packet_classes.get_packets_from_buffer(buffer,
                                                                    packet_class=packet_classes.GSEPacket,
                                                                    start_byte=packet_classes.GSEPacket.START_BYTE)
        packet = packets[0]
        print(('%r' % packet.to_buffer()))
        print((packet.checksum))
        print(('%r' %packet.payload))
        print((packet.payload_length))
        assert (packets[0].to_buffer() == b'\xfa\xff\x01\x00\x00\x00\x01')

        # Interesting corner case - this is a valid packet... except for the unused byte and origin.

    def test_insufficient_length_for_length_byte(self):
        buffer = b'\xfa\xff\x01'
        packets, remainder = packet_classes.get_packets_from_buffer(buffer,
                                                                    packet_class=packet_classes.GSEPacket,
                                                                    start_byte=packet_classes.GSEPacket.START_BYTE)
        assert (remainder == buffer)
        assert (packets == [])

    def test_insufficient_length_for_length_byte_2(self):
        buffer = b'\xfa\xff\x01\x00\x00\x03\x00'
        packets, remainder = packet_classes.get_packets_from_buffer(buffer,
                                                                    packet_class=packet_classes.GSEPacket,
                                                                    start_byte=packet_classes.GSEPacket.START_BYTE)
        assert (remainder == buffer)
        assert (packets == [])

    def test_insufficient_length_for_checksum(self):
        buffer = b'\xfa\xff\x01\x00\x00\x00'
        packets, remainder = packet_classes.get_packets_from_buffer(buffer,
                                                                    packet_class=packet_classes.GSEPacket,
                                                                    start_byte=packet_classes.GSEPacket.START_BYTE)
        assert (remainder == buffer)
        assert (packets == [])

    def test_bad_id_byte(self):
        buffer = b'\xfa\x99\x01\x00\x00\x00\x01'
        packets, remainder = packet_classes.get_packets_from_buffer(buffer,
                                                                    packet_class=packet_classes.GSEPacket,
                                                                    start_byte=packet_classes.GSEPacket.START_BYTE)
        assert (remainder == b'\x99\x01\x00\x00\x00\x01')
        assert (packets == [])

    def test_bad_checksum(self):
        buffer = b'\xfa\xff\x01\x00\x00\x00\x07'
        packets, remainder = packet_classes.get_packets_from_buffer(buffer,
                                                                    packet_class=packet_classes.GSEPacket,
                                                                    start_byte=packet_classes.GSEPacket.START_BYTE)
        assert (remainder == b'\xff\x01\x00\x00\x00\x07')
        assert (packets == [])

    def test_long_sip_packet(self):
        sync = [0xFA, 0xFF]
        header = [0x01, 0x00]
        data = list(range(0, 100))
        length = [0x00, len(data)]  # assumes payload is < 255 bytes
        checksum_data = np.array(header + length + data, dtype='uint8')
        checksum = int(np.sum(checksum_data, dtype='uint8'))
        #print "total sum:", np.sum(checksum_data)
        assert (checksum < 256)
        buffer = np.array(sync + header + length + data + [checksum], dtype='uint8').tobytes()
        packets, remainder = packet_classes.get_packets_from_buffer(buffer,
                                                                    packet_class=packet_classes.GSEPacket,
                                                                    start_byte=packet_classes.GSEPacket.START_BYTE)
        assert (remainder == b'')
        assert (packets[0].to_buffer() == buffer)



class TestFilePackets(unittest.TestCase):
    def setUp(self):
        np.random.seed(0)
        self.random_msg = np.random.randint(0, 255, size=10000).astype('uint8')
        self.random_msg = self.random_msg.tobytes()
        self.random_msg = b'\x02' + self.random_msg[1:]

    def test_run_through_good(self):
        # Tests filepacket
        packets = []
        packet_size = 1000
        num_packets = int(np.ceil(len(self.random_msg) / packet_size))
        for i in range(num_packets):
            msg = self.random_msg[(i * packet_size):((i + 1) * packet_size)]
            packet = packet_classes.FilePacket(file_id=0, packet_number=i,
                                               total_packet_number=num_packets, payload=msg)
            packets.append(packet)

        buffer = b''
        for packet in packets:
            buffer += packet.to_buffer()
        packets_after, remainder = packet_classes.get_packets_from_buffer(buffer, packet_class=packet_classes.FilePacket,
                                                start_byte=packet_classes.FilePacket._valid_start_byte)
        data_buffer = b''.join([packet.payload for packet in packets_after])
        assert (data_buffer == self.random_msg)

        # This needs to be rewritten - assemble_file... does not use FilePacket.
        #g = gse_receiver.GSEReceiver()
        #file_after = g.assemble_file_from_packets(packets_after)
        #assert (np.array_equal(self.random_msg, file_after.payload) == True)

    # def two_files_shuffled_together_test(self):
    #     # Tests two filepackets shuffled together
    #     encoded_data = cobs_encoding.encode_data(self.random_msg, escape_character=constants.SYNC_BYTE)
    #     chunks0 = hirate_sending_methods.chunk_data_by_size(chunk_size=1000, start_byte=constants.SYNC_BYTE, file_id=0,
    #                                                         data=encoded_data)
    #     chunks1 = hirate_sending_methods.chunk_data_by_size(chunk_size=1000, start_byte=constants.SYNC_BYTE, file_id=1,
    #                                                         data=encoded_data)
    #     chunks = chunks0 + chunks1
    #     random.seed(0)
    #     random.shuffle(chunks)
    #     buffer = ''
    #     for chunk in chunks:
    #         buffer += chunk
    #     packets = hirate_receiving_methods.get_packets_from_buffer(buffer, start_byte=chr(constants.SYNC_BYTE))
    #     files = hirate_receiving_methods.packets_to_files(packets)
    #
    #     decoded_data0 = cobs_encoding.decode_data(files[0], escape_character=constants.SYNC_BYTE)
    #     unpacked_data0 = struct.unpack(('%dB' % len(decoded_data0)), decoded_data0)
    #     unpacked_data_array0 = np.array(unpacked_data0).astype('uint8')
    #     assert (np.array_equal(self.random_msg, unpacked_data_array0) == True)
    #
    #     decoded_data1 = cobs_encoding.decode_data(files[1], escape_character=constants.SYNC_BYTE)
    #     unpacked_data1 = struct.unpack(('%dB' % len(decoded_data1)), decoded_data1)
    #     unpacked_data_array1 = np.array(unpacked_data1).astype('uint8')
    #     assert (np.array_equal(self.random_msg, unpacked_data_array1) == True)
