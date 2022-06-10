import os
from skywinder import root_dir
from skywinder.utils.camera_id import get_camera_id

# noinspection PyUnresolvedReferences
c = get_config() # noqa: F821

c.GlobalConfiguration.data_directories = ['/data1', '/data2', '/data3', '/data4']
camera_id = get_camera_id()

# ------------------------------------------------------------------------------
# CommunicatorApp(Application) configuration
# ------------------------------------------------------------------------------

c.Application.log_level = 0

## This is an application.

## Dict for mapping camera ID to Pyro address.e.g. {3: ("pmc-camera-3", 40000)}
c.CommunicatorApp.address_book = {6: ('0.0.0.0', 40000)}
c.Communicator.lowrate_link_parameters = [('comm1', ("localhost", 5001), 5001)]
# Once urls are set, this should look like "('comm1', ("pmc-serial-0", 5001), 5001)"
c.Communicator.hirate_link_parameters = [('highrate', ('localhost', 50002), 700000),
                                         ('los', ('localhost', 50004), 100000)]
# Once urls are set, this should look like "('highrate', ('EXPERIMENT-0', 5002), 700)"

c.GlobalConfiguration.controller_pyro_port = 50001

##
c.GlobalConfiguration.counters_dir = '/var/pmclogs/counters'

##
c.GlobalConfiguration.housekeeping_dir = '/var/pmclogs/housekeeping'

##
c.GlobalConfiguration.log_dir = '/var/pmclogs'

##
c.GlobalConfiguration.pipeline_pyro_port = 50000
c.Communicator.use_controller = False
#c.Communicator.use_controller = True
c.Communicator.initial_leader_id = 6
c.Communicator.initial_peer_polling_order = [6]

c.Communicator.loop_interval = 1
