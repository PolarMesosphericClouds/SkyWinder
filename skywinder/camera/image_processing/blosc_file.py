import logging

import blosc
import numpy as np

from skywinder.camera.pycamera import dtypes

logger = logging.getLogger(__name__)

# We need to ensure blosc uses just 1 thread so that it is always compatible with multiprocessing. This is true as of
#  blosc 1.4.4, but may improve in the future.
original_nthreads = blosc.set_nthreads(1)
logger.debug("Set blosc to use 1 thread, originally was using %d" % original_nthreads)

def load_blosc_file(filename):
    logger.debug("Reading blosc file from %s" % filename)
    with open(filename, 'rb') as fh:
        data = blosc.decompress(fh.read())
    return data

def load_blosc_image(filename):
    data = load_blosc_file(filename)
    image = np.frombuffer(data[:-dtypes.chunk_num_bytes], dtype='uint16')
    image.shape = dtypes.image_dimensions
    chunk_data = np.frombuffer(data[-dtypes.chunk_num_bytes:], dtype=dtypes.chunk_dtype)
    return image, chunk_data


def write_image_blosc(filename,data):
    fh = open(filename,'w')
    compressed_data = blosc.compress(data,shuffle=blosc.BITSHUFFLE,cname='lz4')
    fh.write(compressed_data)
    fh.close()
