from skywinder.communication import pyro_simple_server

host = str(input("Enter an IP address for the server: "))
port = int(input("Enter a port: "))

client = pyro_simple_server.SimpleClient(host, port)
client.main_loop()
