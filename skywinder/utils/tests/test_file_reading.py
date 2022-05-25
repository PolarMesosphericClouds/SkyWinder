from skywinder.utils import file_reading
import tempfile
import unittest
import numpy as np


class FileReadingTest(unittest.TestCase):
    def test_large_file_two_lines(self):
        tfile = tempfile.NamedTemporaryFile()
        buffer = 'a' * 1500
        print(buffer)
        with open(tfile.name, 'w') as f:
            f.write(buffer + '\n')
            f.write(buffer + '\n')
        assert (file_reading.read_last_line(tfile.name) == buffer)

    def test_large_file_one_line(self):
        # ValueError raised if only one line in the file.
        tfile = tempfile.NamedTemporaryFile()
        buffer = 'a' * 1500
        print(buffer)
        with open(tfile.name, 'w') as f:
            f.write(buffer + '\n')
        self.assertRaises(ValueError, file_reading.read_last_line, tfile.name)

    def test_no_newline(self):
        tfile = tempfile.NamedTemporaryFile()
        with open(tfile.name, 'w') as f:
            f.write('a' * 100)
        self.assertRaises(ValueError, file_reading.read_last_line, tfile.name)
