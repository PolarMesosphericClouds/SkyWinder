import Pyro4
Pyro4.config.SERVERTYPE = "multiplex"
Pyro4.config.SERIALIZER = 'pickle'
Pyro4.config.SERIALIZERS_ACCEPTED = ['pickle', ]
# Caution: If COMMTIMEOUT is too low, camera communicator gets a timeout error when it requests data from another communicator.
Pyro4.config.COMMTIMEOUT = 5
# Tests show COMMTIMEOUT works.
# Note that there is another timeout POLLTIMEOUT
# "For the multiplexing server only: the timeout of the select or poll calls"
import select
import time


@Pyro4.expose
class SimpleServer():
    def __init__(self, host='0.0.0.0', port=40000):
        self.host = host
        self.port = port

    def setup_pyro_daemon(self):
        self.pyro_daemon = Pyro4.Daemon(host=self.host, port=self.port)
        uri = self.pyro_daemon.register(self, "communicator")
        print(uri)

    def pyro_loop(self):
        while True:
            events, _, _ = select.select(self.pyro_daemon.sockets, [], [], 0.01)
            if events:
                self.pyro_daemon.events(events)

    def ping(self):
        print('I have been pinged')
        return True


class SimpleClient():
    def __init__(self, host='0.0.0.0', port=40000):
        peer_address = 'PYRO:communicator@%s:%d' % (host, port)
        print('Looking for peer at address %s' % peer_address)
        self.peer = Pyro4.Proxy(peer_address)

    def check_peer(self):
        print('I am pinging my peer')
        self.peer.ping()

    def main_loop(self):
        while True:
            self.check_peer()
            time.sleep(1)
