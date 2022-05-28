import os

BLOCK_SIZE = 1024


def read_last_line(file_):
    buffer = b''
    with open(file_, 'rb') as f:
        f.seek(0, os.SEEK_END)
        file_length = f.tell()
        last_start_offset=0
        while True:
            if last_start_offset + BLOCK_SIZE <= file_length:
                bytes_to_read = BLOCK_SIZE
            else:
                bytes_to_read = file_length-last_start_offset
            if bytes_to_read <= 0:
                raise ValueError("File does not contain a newline")
            f.seek(-last_start_offset-bytes_to_read,os.SEEK_END)
            buffer = f.read(bytes_to_read) + buffer
            last_start_offset = last_start_offset + bytes_to_read
            parts = buffer.split(b'\n')
            if len(parts) >= 3:
                return parts[-2]
