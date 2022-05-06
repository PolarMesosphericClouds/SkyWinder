import os
import orderedattrdict
import serial
import struct
import logging
import time

logger = logging.getLogger(__name__)

magic_incantation = ''.join([chr(x) for x in [0x01, 0x03, 0x00, 0x29, 0x00, 0x23, 0xd5, 0xdb]])

fields = [('header', 'H'),  # 0x0103 2
          ('length', 'B'),  # does not include header, length byte, or CRC 3
          ('cell_temperature_1', 'b'),  # 4
          ('cell_temperature_2', 'b'),  # 5
          ('cell_temperature_3', 'b'),  # 6
          ('cell_temperature_4', 'b'),  # 7
          ('unknown_00_B', 'B'),  # seems to always be 0x0F 8
          ('unknown_01_B', 'B'),  # seen 0xA0 and 0x40 9
          ('unknown_02_H', 'H'),  # seen 0x0000 and 0x0520 11
          ('unknown_03_H', 'H'),  # seen 0x1428 and 0x0000 13
          ('unknown_04_B', 'B'),  # 0x00 14
          ('unknown_05_B', 'B'),  # seen 0x26 and 0x4A 15
          ('unknown_temperature_1', 'b'),  # 16
          ('unknown_temperature_2', 'b'),  # 17
          ('pcb_temperature_1', 'b'),  # 18
          ('pcb_temperature_2', 'b'),  # 19
          ('pcb_temperature_3', 'b'),  # 20
          ('pcb_temperature_4', 'b'),  # 21
          ('unknown_06_H', 'H'),  # seen 0x000D and 0x0040  #23
          ('current_coarse', 'i'),  # 27
          ('current_fine', 'i'),  # 29
          ('cell_voltage_like_thing_1', 'H'),  # 31
          ('cell_voltage_like_thing_2', 'H'),  # 33
          ('total_cell_voltage_1', 'I'),  # 37
          ('total_cell_voltage_2', 'I'),  # 41
          ('state_of_charge_1', 'B'),  # 42
          ('state_of_charge_2', 'B'),  # 43
          ('status_bits_1', 'H'),  # 0x2000  45
          ('unknown_10_H', 'H'),  # 0x0004  47
          ('cell_voltage_1', 'H'),  # 49
          ('cell_voltage_2', 'H'),  # 51
          ('cell_voltage_3', 'H'),  # 53
          ('cell_voltage_4', 'H'),  # 55
          ('cell_voltage_5', 'H'),  # 57
          ('cell_voltage_6', 'H'),  # 59
          ('cell_voltage_7', 'H'),  # 61
          ('cell_voltage_8', 'H'),  # 63
          ('unknown_11_H', 'H'),  # 67
          ('discharge_feedback', 'H'),  # 69
          ('charge_feedback', 'H'),  # 71
          ('unknown_12_H', 'H'),  # always 0 #73
          ('crc16', 'H')  # 75
          ]


def get_field(message, format_code):
    format_code = '<' + format_code
    length = struct.calcsize(format_code)
    result, = struct.unpack(format_code, message[:length])
    return result, message[length:]


def parse_response(message):
    result = orderedattrdict.AttrDict()
    start_index = message.find('\x01\x03')
    if start_index != 0:
        logger.warn("Found unexpected bytes at start of battery message: %r" % (message[:start_index]))
    remainder = message[start_index:]
    next_unknown_field_num = 0
    for name, format_code in fields:
        if not name:
            name = 'unknown_%02d_%s' % (next_unknown_field_num, format_code)
            next_unknown_field_num += 1
        result[name], remainder = get_field(remainder, format_code)
        #print name, len(remainder), result[name]
    return result


class Monitor(object):
    def __init__(self, port='/dev/ttyUSB0', baudrate=115200, timeout=0.5, log_dir='/var/pmclogs/housekeeping/battery',
                 measurement_interval=30):
        self.ser = serial.Serial(port, baudrate=baudrate, timeout=timeout)
        self.log_dir = log_dir
        self.filename = None
        self.file = None
        self.raw_file = None
        self.measurement_interval = measurement_interval
        self.last_epoch = 0

    def read(self):
        self.ser.write(magic_incantation)
        time.sleep(0.1)
        return self.ser.read(self.ser.inWaiting())

    def get_sn(self):
        self.ser.write(''.join([chr(x) for x in [0x01, 0x03, 0x00, 0x01, 0x00, 0x04, 0x15, 0xc9]]))
        time.sleep(0.1)
        return self.ser.read(self.ser.inWaiting())

    def parse(self, message):
        return parse_response(message)

    def create_files(self):
        raw_dir = os.path.join(self.log_dir, 'raw')
        try:
            os.makedirs(self.log_dir)
        except OSError:
            pass
        try:
            os.makedirs(raw_dir)
        except OSError:
            pass
        time_string = time.strftime('%Y-%m-%d_%H%M%S.csv')
        self.filename = os.path.join(self.log_dir, time_string)
        self.raw_filename = os.path.join(raw_dir, time_string)
        self.file = open(self.filename, 'a')
        serial_no = ''.join([('%02X' % ord(x)) for x in self.get_sn()])

        header = ('# Serial No %s\n' % (serial_no))
        self.file.write(header)
        columns = ['epoch'] + [name for (name, _) in fields]
        self.file.write(','.join(columns) + '\n')
        self.file.flush()

        self.raw_file = open(self.raw_filename, 'w')

    def measure_and_log(self):
        if time.time() - self.last_epoch < self.measurement_interval:
            return
        logger.debug("Reading battery status")
        epoch = time.time()
        self.last_epoch = epoch
        raw = self.read()
        result = self.parse(raw)
        self.raw_file.write('%r\n' % raw)
        self.raw_file.flush()
        values = ['%f' % epoch] + [('%d' % value) for value in list(result.values())]
        self.file.write(','.join(values) + '\n')
        self.file.flush()


if __name__ == "__main__":
    m = Monitor()
    m.create_files()
    while True:
        m.measure_and_log()
        time.sleep(1)
