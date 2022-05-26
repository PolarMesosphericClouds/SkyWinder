from skywinder.communication import pyro_simple_server

host = str(input("Enter an IP address for the server: "))
port = int(input("Enter a port: "))

server = pyro_simple_server.SimpleServer(host, port)
server.setup_pyro_daemon()
server.pyro_loop()
