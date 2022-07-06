from skywinder.communication import packet_classes, file_format_classes
import numpy as np


def construct_jpeg(packets):
    sorted_packets = sorted(packets, key=lambda k: k.packet_number)
    packet_length = sorted_packets[0].payload_length
    data_buffer = ''
    packet_number = 0

    for packet in sorted_packets:
        if packet_number == packet.packet_number:
            data_buffer += packet.payload
            packet_number += 1
        else:
            if packet_number < packet.packet_number:
                missing_packets = packet.packet_number - packet_number
                data_buffer += np.zeros(missing_packets * packet_length).astype('uint8').tostring()
                data_buffer += packet.payload
                packet_number = packet.packet_number + 1
            else:
                raise Exception('intended packet_number greater than actual packet_number')

    return data_buffer


def assemble_file_from_packets(self, packets):
    data_buffer = ''.join([packet.payload for packet in packets])
    return file_format_classes.decode_file_from_buffer(data_buffer)


def put_data_into_packets(buffer, file_id, packet_size=1000):
    packets = []
    num_packets = int(np.ceil(len(buffer) / packet_size))
    for i in range(num_packets):
        msg = buffer[(i * packet_size):((i + 1) * packet_size)]
        packet = packet_classes.FilePacket(file_id=file_id, packet_number=i,
                                           total_packet_number=num_packets, payload=msg)
        packets.append(packet)
    return packets


def get_data_for_example():
    with open('2017-07-25_174523_002255.jpg', 'rb') as f:
        buffer = f.read()
    return buffer


def run_example():
    buffer = get_data_for_example()
    packets = put_data_into_packets(buffer, 1)
    partial_packets = packets[:3] + packets[5:]
    j2 = construct_jpeg(partial_packets)
    with open('/home/bjorn/jpeg_filler_example.jpg', 'wb') as f:
        f.write(j2)

if __name__ == "__main__":
    run_example()
