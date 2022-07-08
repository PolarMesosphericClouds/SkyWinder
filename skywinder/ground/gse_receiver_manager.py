import logging
import os
import time

import Pyro4
import sys
from traitlets import (Float, List, Enum, Unicode, Int)
from traitlets.config import Application
from skywinder.utils.configuration import default_ground_config_dir

from skywinder.ground.ground_configuration import GroundConfiguration
from skywinder.ground.gse_receiver import GSEReceiver

print(Pyro4.config.SERIALIZER, Pyro4.config.SERIALIZERS_ACCEPTED, Pyro4.config.SERVERTYPE)

logger = logging.getLogger(__name__)

OPENPORT = 'openport'
GSE_SIP = 'gse_sip'
LOS = 'los'
TDRSS_DIRECT = 'tdrss_direct'

@Pyro4.expose
class GSEReceiverManager(GroundConfiguration):
    downlinks_to_use = List(Enum((OPENPORT,GSE_SIP,LOS,TDRSS_DIRECT)),
                            default_value=['openport','gse_sip', 'los'],
                            help="Downlinks to setup and use.").tag(config=True)
    receiver_main_loop_interval = Float(1.0,min=0).tag(config=True)

    def __init__(self, **kwargs):
        super(GSEReceiverManager,self).__init__(**kwargs)
        timestring = time.strftime('%Y-%m-%d_%H%M%S')
        self.data_path = os.path.join(self.root_data_path.decode('ascii'),timestring)
        self.receivers = {}
        for link_name in self.downlinks_to_use:
            parameters = self.downlink_parameters[link_name]
            use_gse_packets = (link_name == GSE_SIP)
            try:
                receiver = GSEReceiver(root_path=self.data_path,serial_port_or_socket_port=parameters['port'],
                                                        baudrate=parameters['baudrate'], loop_interval=parameters['loop_interval'],
                                                        use_gse_packets=use_gse_packets,name=link_name)
                log.setup_file_handler(link_name,logger=receiver.logger)
                self.receivers[link_name] = receiver
                receiver.start_main_loop_thread()
            except OSError:
                logger.exception("Failed to setup link %s" % link_name)

    def get_file_status(self):
        result = {}
        for link_name,gse in list(self.receivers.items()):
            result[link_name] = gse.get_file_status()
        return result





class GSEReceiverManagerApp(Application):
    config_file = Unicode('', help="Load this config file").tag(config=True)
    config_dir = Unicode(default_ground_config_dir, help="Config file directory").tag(config=True)
    write_default_config = Unicode('', help="Write template config file to this location").tag(config=True)
    classes = List([GSEReceiverManager])
    pyro_port = Int(default_value=55000,min=1024,max=65535).tag(config=True)
    mode = Enum(['full', 'piggyback', 'piggyback_sim', 'los', 'palestine'],default_value='full', help="configuration shortcut to setup for piggyback or full system").tag(config=True)
    aliases = dict(generate_config='GSEReceiverManagerApp.write_default_config',
                   config_file='GSEReceiverManagerApp.config_file',
                   mode='GSEReceiverManagerApp.mode')

    def initialize(self, argv=None):
        actual_argv = argv
        if argv is None:
            actual_argv = sys.argv
        print("initializing GSEReceiver with arguments:",actual_argv)
        self.parse_command_line(argv)
        if self.write_default_config:
            with open(self.write_default_config, 'w') as fh:
                fh.write(self.generate_config_file())
                self.exit()
        if self.config_file:
            print("**** Ignoring any --mode option ****")
        else:
            if self.mode == 'full':
                print("Using full configuration mode")
                self.config_file = 'default_ground_config.py'
            elif self.mode == 'piggyback':
                print("Using piggyback configuration mode")
                self.config_file = 'piggyback_ground_config.py'
            elif self.mode == 'piggyback_sim':
                print("Using piggyback simulator configuration mode")
                self.config_file = 'simulated_piggyback_ground_config.py'
            elif self.mode == 'los':
                print("Using remote LOS configuration mode")
                self.config_file = 'los_ground_config.py'
            elif self.mode == 'palestine':
                print("Using palestine configuration mode")
                self.config_file = 'palestine_config.py'
            else:
                raise RuntimeError("Unexpected usage: either specify --config_file or use a valid --mode option")
        print('loading config: ', self.config_dir, self.config_file)
        self.load_config_file(self.config_file, path=self.config_dir)

        print(self.config)
        self.manager = GSEReceiverManager(config=self.config)



if __name__ == "__main__":
    from skywinder.utils import log
    log.setup_stream_handler(logging.DEBUG)
    app = GSEReceiverManagerApp()
    app.initialize()
    gserm = app.manager
    daemon = Pyro4.Daemon('0.0.0.0',app.pyro_port)
    daemon.register(gserm,'gserm')
    daemon.requestLoop()
