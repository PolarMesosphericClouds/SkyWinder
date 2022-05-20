import numpy as np
import struct


def generate_random_bytes(length):
    np.random.seed(0)
    return np.random.randint(0,255,size=length).astype('uint8').tostring()


def generate_good_start_end_junk_data(length=100):
    format_string = '<1B%ds1B' % length
    junk_data = generate_random_bytes(length)
    return struct.pack(format_string, 0x10, junk_data, 0x03)


def generate_start_junk(length=100):
    format_string = '<1B%ds' % length
    junk_data = generate_random_bytes(length)
    return struct.pack(format_string, 0x10, junk_data)


def generate_end_junk(length=100):
    format_string = '<%ds1B' % length
    junk_data = generate_random_bytes(length)
    return struct.pack(format_string, junk_data, 0x03)
