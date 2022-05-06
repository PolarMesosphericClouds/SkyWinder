import os
import time
import select
import Pyro4
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)

from pymodbus.constants import Defaults
Defaults.Timeout = 1
from pymodbus.client.sync import ModbusTcpClient


LOG_DIR = '/var/pmclogs/housekeeping/charge_controller'
# serial_number = 16050331
device_name = 'TriStar-MPPT-60'
NUM_REGISTERS = 92
# FIRST_BATCH_START = 5403
# NUM_EEPROM_REGISTERS_FIRST_BATCH = 7
# SECOND_BATCH_START = 57344
# NUM_EEPROM_REGISTERS_SECOND_BATCH = 34
# THIRD_BATCH_START = 57472
# NUM_EEPROM_REGISTERS_THIRD_BATCH = 13


EEPROM_BATCH_1 = (0x151B, 0x1521 + 1)
EEPROM_BATCH_2 = (0xE000, 0xE021 + 1)
EEPROM_BATCH_3 = (0xE080, 0xE0CD + 1)
EEPROM_REGISTER_INDICES = list(range(*EEPROM_BATCH_1)) + list(range(*EEPROM_BATCH_2)) + list(range(*EEPROM_BATCH_3))

NUM_COIL_REGISTERS = 26


@Pyro4.expose
class ChargeController():
    def __init__(self, address):
        self.host,self.port = address
        self.device_name = '<unknown>'
        self.serial_number = '<unknown>'
        self.update_serial_number_and_device_name()
        self.readable_values = {}
        self.coil_register_indices = list(range(1, NUM_COIL_REGISTERS + 1))

    def update_serial_number_and_device_name(self):
        try:
            self.measure_eeprom()
            serial_number_bytes = [('%04x' % self.eeprom_measurement[k])[::-1] for k in range(57536, 57540)]
            self.serial_number = ''.join(serial_number_bytes)[::2]
            device_model = self.eeprom_measurement[0xE0CC]
            if device_model:
                self.device_name = 'TriStar-MPPT-60'
            else:
                self.device_name = 'TriStar-MPPT-45'
        except Exception:
            logger.exception("Could not get serial number or device name for %s:%d" % (self.host,self.port))

    def measure(self):
        self.client = ModbusTcpClient(host=self.host, port=self.port)
        measurement = OrderedDict(epoch=time.time())
        result = self.client.read_input_registers(0, NUM_REGISTERS, unit=0x01,)
        try:
            measurement.update(list(zip(list(range(NUM_REGISTERS)), result.registers)))
        except AttributeError as e:
            print(e, result)
            raise
        self.measurement = measurement
        self.client.close()
        return self.measurement

    def measure_eeprom(self):
        self.client = ModbusTcpClient(host=self.host, port=self.port)
        self.eeprom_measurement = OrderedDict(epoch=time.time())
        eeprom_measurement = self.client.read_input_registers(EEPROM_BATCH_1[0], EEPROM_BATCH_1[1] - EEPROM_BATCH_1[0],
                                                              unit=0x01).registers
        eeprom_measurement += self.client.read_input_registers(EEPROM_BATCH_2[0], EEPROM_BATCH_2[1] - EEPROM_BATCH_2[0],
                                                               unit=0x01).registers
        eeprom_measurement += self.client.read_input_registers(EEPROM_BATCH_3[0], EEPROM_BATCH_3[1] - EEPROM_BATCH_3[0],
                                                               unit=0x01).registers
        self.eeprom_measurement.update(list(zip(EEPROM_REGISTER_INDICES, eeprom_measurement)))
        self.client.close()
        return self.eeprom_measurement

    def measure_coils(self):
        self.coil_measurement = OrderedDict(epoch=time.time())
        self.coil_measurement.update(
            list(zip(list(range(NUM_COIL_REGISTERS)), self.client.read_coils(0, NUM_COIL_REGISTERS, unit=0x01).bits)))
        return self.coil_measurement


@Pyro4.expose
class ChargeControllerLogger():
    def __init__(self, address=('pmc-charge-controller-0',502), measurement_interval=10, record_eeprom=True,
                 eeprom_measurement_interval=3600, pyro_port=None, log_dir=''):
        try:
            os.makedirs(log_dir)
        except OSError:
            pass
        self.log_dir = log_dir
        self.charge_controller = ChargeController(address)
        self.filename = None
        self.name = address[0].replace('.','_')
        self.file = None
        self.last_measurement = None
        self.last_measurement_attempt_epoch = 0
        self.last_eeprom_measurement = None
        self.measurement_interval = measurement_interval
        self.record_eeprom = record_eeprom
        if self.record_eeprom:
            self.eeprom_measurement_interval = eeprom_measurement_interval
            self.eeprom_filename = None
            self.eeprom_file = None
        if pyro_port:
            self.daemon = Pyro4.Daemon(host='0.0.0.0', port=pyro_port)
            print(self.daemon.register(self, objectId='chargecontroller'))

    def create_file(self):
        self.filename = os.path.join(self.log_dir, (self.name + '_register_' + time.strftime('%Y-%m-%d_%H%M%S.csv')))
        self.file = open(self.filename, 'a')
        header = ('# %s Serial No %s\n' % (self.charge_controller.device_name, self.charge_controller.serial_number))
        self.file.write(header)
        columns = ['epoch'] + [('register_%03d' % x) for x in range(1, NUM_REGISTERS + 1)]
        self.file.write(','.join(columns) + '\n')
        self.file.flush()

    def create_eeprom_file(self):
        self.eeprom_filename = os.path.join(self.log_dir, (self.name + '_eeprom_' + time.strftime('%Y-%m-%d_%H%M%S.csv')))
        self.eeprom_file = open(self.eeprom_filename, 'a')
        header = ('# %s Serial No %s\n' % (self.charge_controller.device_name, self.charge_controller.serial_number))
        self.eeprom_file.write(header)
        columns = ['epoch'] + [('eeprom_%d' % x) for x in EEPROM_REGISTER_INDICES]
        self.eeprom_file.write(','.join(columns) + '\n')
        self.eeprom_file.flush()

    def show_priority_values(self):
        return populate_human_readable_dict(self.last_measurement)

    def measure_and_log(self):
        if time.time() - self.last_measurement_attempt_epoch < self.measurement_interval:
            return
        self.last_measurement_attempt_epoch = time.time()
        if self.last_measurement and (time.time() - self.last_measurement['epoch'] < self.measurement_interval):
            return
        try:
            self.last_measurement = self.charge_controller.measure()
        except AttributeError:
            pass
        else:
            if self.file is None:
                self.create_file()
            line_to_write = '%f,' % list(self.last_measurement.values())[0]
            line_to_write += (','.join([('%d' % x) for x in list(self.last_measurement.values())[1:]]) + '\n')
            self.file.write(line_to_write)
            self.file.flush()

        if self.record_eeprom:
            if (self.last_eeprom_measurement == None) or (
                            time.time() - self.last_eeprom_measurement['epoch'] > self.eeprom_measurement_interval):
                if self.eeprom_file is None:
                    self.create_eeprom_file()
                try:
                    self.last_eeprom_measurement = self.charge_controller.measure_eeprom()
                except AttributeError:
                    pass
                else:
                    line_to_write = '%f,' % list(self.last_eeprom_measurement.values())[0]
                    line_to_write += (','.join([('%d' % x) for x in list(self.last_eeprom_measurement.values())[1:]]) + '\n')
                    self.eeprom_file.write(line_to_write)
                    self.eeprom_file.flush()

    def run(self):
        self.measure_and_log()
        while time.time() - self.last_measurement['epoch'] < self.measurement_interval:
            events, _, _ = select.select(self.daemon.sockets, [], [], 0.1)
            if events:
                self.daemon.events(events)


def populate_human_readable_dict(measurement_array):
    priority_values = {}
    epoch = measurement_array[0]
    voltage_scaling = measurement_array[1] + (measurement_array[2] / 16.)
    current_scaling = measurement_array[3] + (measurement_array[4] / 16.)
    priority_values['epoch'] = epoch
    priority_values['battery_voltage'] = measurement_array[25] * voltage_scaling * 2. ** -15
    priority_values['solar_voltage'] = measurement_array[28] * voltage_scaling * 2. ** -15
    priority_values['battery_current'] = measurement_array[29] * current_scaling * 2. ** -15
    priority_values['solar_current'] = measurement_array[30] * current_scaling * 2. ** -15
    priority_values['charge_state'] = measurement_array[51]
    priority_values['target_voltage'] = measurement_array[52] * voltage_scaling * 2. ** -15
    priority_values['output_power'] = measurement_array[59] * voltage_scaling * current_scaling * 2. ** -17
    priority_values['heatsink_t'] = measurement_array[36]
    priority_values['battery_t'] = measurement_array[38]

    return priority_values


def run_charge_controller_logger(address=('pmc-charge-controller-0', 502), measurement_interval=10, record_eeprom=True,
                 eeprom_measurement_interval=3600, pyro_port=42000,log_dir=LOG_DIR):
    ccl = ChargeControllerLogger(address=address,measurement_interval=measurement_interval,record_eeprom=record_eeprom,
                                 eeprom_measurement_interval=eeprom_measurement_interval,pyro_port=pyro_port,log_dir=log_dir)
    ccl.run()

if __name__ == "__main__":
    import sys
    charge_controller = 0
    try:
        charge_controller = int(sys.argv[1])
    except (IndexError, ValueError):
        pass
    run_charge_controller_logger('pmc-charge-controller-%d' % charge_controller)
