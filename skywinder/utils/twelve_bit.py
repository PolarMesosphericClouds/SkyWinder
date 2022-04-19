import numpy as np

def read_12_bit_file(filename,dimensions=(3232,4864)):
    bytes = np.fromfile(filename,dtype=np.uint8)
    nbytes = bytes.shape[0]
    assert (nbytes*8) % 12 == 0 # ensure we're working with a multiple of 12 bits
    n12words = nbytes*8 // 12
    output = np.zeros((n12words,),dtype=np.uint16)
    output[::2] = np.uint16(bytes[::3])*16 + np.uint16(bytes[1::3] // 16)
    output[1::2] = np.uint16(bytes[1::3] & 0x0f) + np.uint16(bytes[2::3])*16
    return output.reshape((dimensions))

def unpack_12_bit(data,dimensions=(3232,4864)):
    nbytes = data.shape[0]
    assert (nbytes*8) % 12 == 0 # ensure we're working with a multiple of 12 bits
    n12words = nbytes*8 // 12
    output = np.zeros((n12words,),dtype=np.uint16)
    output[::2] = np.uint16(data[::3])*16 + np.uint16(data[1::3] // 16)
    output[1::2] = np.uint16(data[1::3] & 0x0f) + np.uint16(data[2::3])*16
    return output.reshape((dimensions))

