import skywinder.communication.command_table
from skywinder.ground import commanding
from skywinder.ground.ground_configuration import GroundConfiguration
from skywinder.utils.log import setup_stream_handler, setup_file_handler
import logging
import socket
logger = logging.getLogger('skywinder.ground')
setup_stream_handler(level=logging.DEBUG)

class LidarCommandRelay(GroundConfiguration):
    def __init__(self,command_sender_app,**kwargs):
        super(LidarCommandRelay,self).__init__(**kwargs)
        self.command_sender_app = command_sender_app
        self.command_sender = self.command_sender_app.command_sender
        self.socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        self.socket.setblocking(True)
        self.socket.bind(self.lidar_command_relay_address)
        self.socket.listen(1)
    def run(self):
        while True:
            logger.info("Waiting for a connection")
            connection, client_address = self.socket.accept()
            try:
                logger.info("Connection from %s" % str(client_address))
                remainder = ''
                done = False
                while not done:
                    logger.info("Reading data")
                    new_data = connection.recv(1024)
                    logger.info("Got %r" % new_data)
                    if new_data == '':
                        done=True
                        end_index = len(remainder)
                    else:
                        remainder = remainder + new_data
                        end_index = remainder.find('\x04')
                    if end_index >= 0:
                        command = remainder[:end_index]
                        logger.info("got command %r" % command)
                        if len(command) <= 248:
                            self.command_sender.send(self.command_sender.command_manager.send_lidar_command(command=command),
                                                     destination=skywinder.communication.command_table.DESTINATION_LIDAR)
                        else:
                            logger.warning("Received command is %d bytes long, greater than maximum 248 bytes, so will be dropped" %
                                           len(command))
                        if len(remainder)>end_index+1:
                            remainder = remainder[end_index+1:]
                        else:
                            remainder = ''
            finally:
                connection.close()



def main():
    command_sender_app = commanding.CommandSenderApp()
    command_sender_app.initialize()
    lidar_command_relay = LidarCommandRelay(command_sender_app=command_sender_app)
    lidar_command_relay.run()

if __name__ == '__main__':
    main()
