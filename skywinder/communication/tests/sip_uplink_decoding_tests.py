import unittest

from skywinder.communication.uplink_classes import get_sip_uplink_packets_from_buffer



class TestSIPUplinkDecoding(unittest.TestCase):
    def setUp(self):
        return

    def tearDown(self):
        return

    def test_empty_buffer(self):
        buffer = ''
        packets, remainder = get_sip_uplink_packets_from_buffer(buffer)
        self.assertEqual(packets, [])
        self.assertEqual(remainder, '')

    def test_science_request(self):
        buffer = '\x10\x13\x03'
        packets, remainder = get_sip_uplink_packets_from_buffer(buffer)
        self.assertEqual(packets, ['\x10\x13\x03'])
        self.assertEqual(remainder, '')

    def test_solo_start_byte(self):
        buffer = '\x10'
        packets, remainder = get_sip_uplink_packets_from_buffer(buffer)
        self.assertEqual(packets, [])
        self.assertEqual(remainder, '\x10')

    def test_separated_science_request_packet(self):
        buffer = '\x10\x13'
        packets, remainder = get_sip_uplink_packets_from_buffer(buffer)
        self.assertEqual(packets, [])
        self.assertEqual(remainder, '\x10\x13')

    def test_separated_science_command_packet(self):
        buffer = '\x10\x14'
        packets, remainder = get_sip_uplink_packets_from_buffer(buffer)
        self.assertEqual(packets, [])
        self.assertEqual(remainder, '\x10\x14')

    def test_truncated_science_command_packet(self):
        buffer = '\x10\x14\x06'
        packets, remainder = get_sip_uplink_packets_from_buffer(buffer)
        self.assertEqual(packets, [])
        self.assertEqual(remainder, '\x10\x14\x06')

    def test_good_science_command_byte(self):
        buffer = '\x10\x14\x06\x00\x00\x00\x00\x00\x00\x03'
        packets, remainder = get_sip_uplink_packets_from_buffer(buffer)
        self.assertEqual(packets, ['\x10\x14\x06\x00\x00\x00\x00\x00\x00\x03'])
        self.assertEqual(remainder, '')

    def test_lost_end1(self):
        buffer = '\x10\x14\x06\x00\x10\x13\x03'
        packets, remainder = get_sip_uplink_packets_from_buffer(buffer)
        self.assertEqual(packets, [])
        self.assertEqual(remainder, '\x10\x14\x06\x00\x10\x13\x03')

    def test_science_in_middle_valid_end_byte(self):
        buffer = '\x10\x14\x06\x00\x10\x13\x03\x00\x00\x03'
        packets, remainder = get_sip_uplink_packets_from_buffer(buffer)
        self.assertEqual(packets, ['\x10\x14\x06\x00\x10\x13\x03\x00\x00\x03'])
        self.assertEqual(remainder, '')

    def test_science_request_in_middle_invalid_end_byte(self):
        buffer = '\x10\x14\x06\x00\x10\x13\x03\x00\x00\x55'
        packets, remainder = get_sip_uplink_packets_from_buffer(buffer)
        self.assertEqual(packets, ['\x10\x13\x03'])
        self.assertEqual(remainder, '')

    def test_lost_end2(self):
        buffer = '\x10\x14\x06\x00\x00\x00\x00\x00\x00\x10\x13\x03'
        packets, remainder = get_sip_uplink_packets_from_buffer(buffer)
        self.assertEqual(packets, ['\x10\x13\x03'])
        self.assertEqual(remainder, '')

    def test_lost_end3(self):
        buffer = '\x10\x14\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x13\x03'
        packets, remainder = get_sip_uplink_packets_from_buffer(buffer)
        self.assertEqual(packets, ['\x10\x13\x03'])
        self.assertEqual(remainder, '')

    def test_lost_end_no_byte(self):
        buffer = '\x10\x14\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        packets, remainder = get_sip_uplink_packets_from_buffer(buffer)
        self.assertEqual(packets, [])
        self.assertEqual(remainder, '')

    def test_crap_at_beginning(self):
        buffer = '\x00\x00\x00\x00\x10\x13\x03'
        packets, remainder = get_sip_uplink_packets_from_buffer(buffer)
        self.assertEqual(packets, ['\x10\x13\x03'])
        self.assertEqual(remainder, '')

    def test_no_start_byte(self):
        buffer = '\x00\x00\x00\x00'
        packets, remainder = get_sip_uplink_packets_from_buffer(buffer)
        self.assertEqual(packets, [])
        self.assertEqual(remainder, '')

    def test_bad_id(self):
        buffer = '\x10\x26\x03'
        packets, remainder = get_sip_uplink_packets_from_buffer(buffer)
        self.assertEqual(packets, [])
        self.assertEqual(remainder, '')

    def test_bad_end_byte_science_request(self):
        buffer = '\x10\x13\x00'
        packets, remainder = get_sip_uplink_packets_from_buffer(buffer)
        self.assertEqual(packets, [])
        self.assertEqual(remainder, '')

    def test_bad_end_byte_science_request_another_byte(self):
        buffer = '\x10\x13\x10\x13\x03'
        packets, remainder = get_sip_uplink_packets_from_buffer(buffer)
        self.assertEqual(packets, ['\x10\x13\x03'])
        self.assertEqual(remainder, '')

    def test_multiple_reads(self):
        data = ['\x10\x14\x1b\x00\x04\x00\n\x00\x00\x00',
                "d\x00\x00\x03\xe8\x00\x00'\x10\xff",
                '\xff\xff\xff\xff\xff\xff\xff\xffs5',
                '\x03']
        for k in range(len(data)):
            received_so_far = ''.join(data[:k+1])
            packets, remainder = get_sip_uplink_packets_from_buffer(received_so_far)
            if k == len(data)-1:
                assert packets[0] == received_so_far
                assert remainder == ''
            else:
                assert packets == []
                assert remainder == received_so_far

