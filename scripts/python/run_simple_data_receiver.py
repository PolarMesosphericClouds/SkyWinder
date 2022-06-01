import time
import socket

port = int(input("Enter a port: "))

socket_ = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
socket_.bind(('0.0.0.0', port))
socket_.settimeout(0)

while True:
    try:
        data = socket_.recv(2000)
        print(data)
        time.sleep(1)
    except socket.error as e:
        print('No data received')
        time.sleep(1)
        pass
