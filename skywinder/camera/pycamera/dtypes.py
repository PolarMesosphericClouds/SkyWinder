import numpy as np

image_dimensions = (3232,4864)

frame_info_dtype = np.dtype([('frame_id',np.uint64),('timestamp',np.uint64),
                             ('frame_status',np.uint32), ('is_filled', np.uint32)])

chunk_dtype = np.dtype([('image_chunk_identifier','<u4'),  # NB: This is part of the GigEVision chunk header, so order
                        ('image_chunk_length','<u4'),     # is little endian instead of big endian
                        ('acquisition_count', '>u4'),
                        ('lens_status_focus','>u2'),
                        ('lens_aperture','u1'),
                        ('lens_focal_length','u1'),
                        ('exposure_us','>u4'),
                        ('gain_db','>u4'),
                        ('sync_in','>u2'),
                        ('sync_out','>u2'),
                        ('reserved_1','>u4'),
                        ('reserved_2','>u4'),
                        ('reserved_3','>u4'),
                        ('reserved_4','>u4'),
                        ('reserved_5','>u4'),
                        ('chunk_identifier','<u4'),  # NB: This is part of the GigEVision chunk header, so order
                        ('chunk_length','<u4')])     # is little endian instead of big endian

chunk_num_bytes = chunk_dtype.itemsize

def decode_aperture_chunk_data(chunk_data_aperture_byte):
    """
    Convert value provided in byte 7 of chunk data to FStop number

    Formula provided on page 100 of GigE_Features_Reference.pdf (v5.3.2)
    https://www.alliedvision.com/fileadmin/content/documents/products/cameras/various/features/GigE_Features_Reference.pdf

    Parameters
    ----------
    chunk_data_aperture_byte: int 0-255
        value of chunk data byte 7, called chunk_dtype['lens_aperture']

    Returns
    -------
    fstop: float

    """
    return 2**((chunk_data_aperture_byte - 8) / 16.0)


_lens_status_error_message_strings = {0: "No error",
                                      1: "Lens failed query by camera",
                                      2: "Lens communication error 2 (can occur when removing lens)",
                                      3: "Lens communication error 3 (can occur when removing lens)",
                                      4: "Lens remained busy for longer than 10 seconds",
                                      5: "Lens focus zero stop not detected",
                                      6: "Lens focus infinity stop not detected"}
def decode_lens_status_chunk_data(status_bits):
    """

    Parameters
    ----------
    chunk_data_lens_status_byte : int 0-63
        value of top 6 bits of chunk data byte 5, stored in image index as 'lens_status' and equal to chunk_dtype['lens_status_focus']>>10

    Returns
    -------
    status dictionary with keys 'error', 'lens_attached', 'auto_focus', 'last_error', 'last_error_message'

    """
    last_error= (status_bits & 0x7)
    last_error_message = _lens_status_error_message_strings.get(last_error,("Unexpected eror code %d" % last_error))
    result = dict(error = bool(status_bits & 0x20),
                  lens_attached=bool(status_bits & 0x10),
                  auto_focus=bool(status_bits & 0x08),
                  last_error = last_error,
                  last_error_message=last_error_message)
    return result