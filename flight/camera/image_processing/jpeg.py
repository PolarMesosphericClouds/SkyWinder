import numpy as np
import io
from PIL import Image


def fast_8bit_image(array):
    return Image.fromarray((array // 2 ** 8).astype('uint8'))


def numpy_to_image(array):
    return Image.fromarray(array.astype('int32'), mode='I')


def simple_jpeg(array, scale_by=1, resample=0, **kwargs):
    _ = kwargs.pop('format', None)  # remove duplicate format specifier
    img = Image.fromarray(array.astype('int32'), mode='I')
    if scale_by != 1:
        x, y = array.shape
        x = int(x * scale_by)
        y = int(y * scale_by)
        size = (y, x)
        img = img.resize(size, resample=resample)
    img = np.asarray(img, dtype='int32')
    min_ = img.min()
    img = img - min_
    max_ = img.max()
    scale = 1
    if max_ > 255:
        scale = (255. / max_)
        img = img * scale
    img = Image.fromarray(img.astype('uint8'), mode='L')
    stream = io.StringIO()
    img.save(stream, format='jpeg', **kwargs)
    stream.seek(0)
    return stream.read(), min_, scale


def image_from_string(data):
    stream = io.StringIO(data)
    stream.seek(0)
    return Image.open(stream)
