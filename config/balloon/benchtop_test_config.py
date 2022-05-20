import os
from skywinder_streamlined_flight_control import root_dir
#from skywinder.utils.camera_id import get_camera_id

# noinspection PyUnresolvedReferences
c = get_config() # # noqa: F821

c.GlobalConfiguration.data_directories = ['/data1', '/data2', '/data3', '/data4']
#camera_id = get_camera_id()
camera_id = 255

# ------------------------------------------------------------------------------
# CommunicatorApp(Application) configuration
# ------------------------------------------------------------------------------

c.Application.log_level = 0

## This is an application.

## Dict for mapping camera ID to Pyro address.e.g. {3: ("pmc-camera-3", 40000)}
c.CommunicatorApp.address_book = {0: ('pmc-camera-0', 40000), 1: ('pmc-camera-1', 40000),
                                  2: ('pmc-camera-2', 40000), 3: ('pmc-camera-3', 40000),
                                  4: ('pmc-camera-4', 40000), 5: ('pmc-camera-5', 40000),
                                  6: ('pmc-camera-6', 40000), 7: ('pmc-camera-7', 40000),
                                  255: ('0.0.0.0', 40000)}

c.Communicator.hirate_link_parameters = [('highrate', ('localhost', 50002), 700000),
                                         ('openport', ('localhost', 45001), 1000000),
                                         ('los', ('localhost', 50004), 100000)]

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
c.Communicator.initial_peer_polling_order = [255]
c.Communicator.short_status_order = [camera_id]

c.Communicator.charge_controller_settings = []

c.Communicator.battery_monitor_port = ""
##

c.Communicator.peers_with_battery_monitors = []

c.Communicator.narrowfield_cameras = []
c.Communicator.widefield_cameras = [camera_id]
c.Communicator.loop_interval = 1
