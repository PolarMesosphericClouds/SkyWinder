import time
import os
import numpy as np
import serial
import pynmea2

LOG_DIR = '/var/pmclogs/housekeeping/gps'

if os.path.exists('/dev/ttyACM0'):
    SERIAL_PORT = '/dev/ttyACM0'
else:
    SERIAL_PORT = '/dev/ttyUSB0'

class GPSLogger():
    def __init__(self, serial_port=SERIAL_PORT, baudrate=4800, measurement_interval=5):
        self.serial = serial.Serial(port=serial_port,baudrate=baudrate,timeout=0)
        self.streamer =pynmea2.NMEAStreamReader(self.serial,errors='yield')
        try:
            os.makedirs(LOG_DIR)
        except OSError:
            pass
        self.filename = None
        self.file = None
        self.measurement_interval = measurement_interval
        self.filename = os.path.join(LOG_DIR,(time.strftime('%Y-%m-%d_%H%M%S.csv')))
        with open(self.filename,'w') as fh:
            fh.write("# %s\n" % self.serial.port)
        self.last_fragment = ''
        self.last_timestamp = time.time()

    def run(self):
        while True:
            timestamp = time.time()
            try:
                for msg in next(self.streamer):
                    msg_str = str(msg)
                    if msg_str:
                        with open(self.filename,'a') as fh:
                            fh.write("%f,%r\n" % (timestamp,msg_str))
                time.sleep(0.01)
            except UnicodeDecodeError:  # This can occur when a garbled partial message is received
                pass



if __name__ == "__main__":

    gps = GPSLogger()
    gps.run()