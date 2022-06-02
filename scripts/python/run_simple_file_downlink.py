from skywinder.communication import downlink_classes, file_format_classes
from skywinder.communication import constants
import time

host = str(input("Enter an IP address for the server: "))
port = int(input("Enter a port: "))

initial_rate = 10000
name = 'test_downlink'

link = downlink_classes.HirateDownlink(ip=host, port=port, speed_bytes_per_sec=initial_rate, name=name)

def get_file():
    # Read the file you want here
    return b'fake data ' * 1000

buffer = get_file()

file_format_classes.GeneralFile(payload=buffer, filename='test.txt', timestamp=123.1, camera_id=2,
                                        request_id=535)

file_id = 535

link.put_data_into_queue(buffer, file_id)

while link.packets_to_send:
    print('Sending packet')
    link.send_data()
    print(len(link.packets_to_send))
    time.sleep(1)
