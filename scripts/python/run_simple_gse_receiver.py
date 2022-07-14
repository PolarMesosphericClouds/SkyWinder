import logging
from skywinder.ground import gse_receiver
from skywinder.utils import log

name = 'simple_receiver'

gse_logger = logging.getLogger('skywinder.'+name)
gse_logger.setLevel(logging.DEBUG)
gse_logger.addHandler(log.default_handler)
log.default_handler.setLevel(logging.DEBUG)
gse_logger.info("Stream handler initialized for %s" % gse_logger.name)

g = gse_receiver.GSEReceiver(root_path = './gse_data', serial_port_or_socket_port = 40000,
                             baudrate=115200, loop_interval=.1, use_gse_packets=True, name=name)

g.main_loop()