from skywinder.communication import downlink_classes
from skywinder.communication import constants
import time

host = str(input("Enter an IP address for the server: "))
port = int(input("Enter a port: "))

initial_rate = 10000
name = 'test_downlink'

link = downlink_classes.HirateDownlink(ip=host, port=port, speed_bytes_per_sec=initial_rate, name=name)

buffer = b'hello' * 1000
#buffer = bytes([constants.SIP_START_BYTE]) + bytes([constants.SCIENCE_DATA_REQUEST_MESSAGE]) + bytes([constants.SIP_END_BYTE])
# For constructing SIP commands in the future

file_id = 1

link.put_data_into_queue(buffer, file_id)

while link.packets_to_send:
    print('Sending packet')
    link.send_data()
    print(len(link.packets_to_send))
    time.sleep(1)
