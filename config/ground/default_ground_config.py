# Configuration file for application.

# noinspection PyUnresolvedReferences
c = get_config()

# ------------------------------------------------------------------------------
# Application(SingletonConfigurable) configuration
# ------------------------------------------------------------------------------

## This is an application.

## The date format used by logging formatters for %(asctime)s
# c.Application.log_datefmt = '%Y-%m-%d %H:%M:%S'

## The Logging format template
# c.Application.log_format = '[%(name)s]%(highlevel)s %(message)s'

## Set the log level by value or name.
# c.Application.log_level = 30

# ------------------------------------------------------------------------------
# CommandSenderApp(Application) configuration
# ------------------------------------------------------------------------------

## This is an application.

## Config file directory
# c.CommandSenderApp.config_dir = '/home/pmc/pmchome/pmc-turbo-devel/config/ground'

## Load this config file
# c.CommandSenderApp.config_file = u'default_ground_config.py'

## Write template config file to this location
# c.CommandSenderApp.write_default_config = u''

# ------------------------------------------------------------------------------
# GroundConfiguration(Configurable) configuration
# ------------------------------------------------------------------------------

## 
# c.GroundConfiguration.command_history_subdir = 'command_history'

## 
# c.GroundConfiguration.command_index_filename = 'index.csv'

## Serial device connected to GSE uplink
c.GroundConfiguration.command_port = b'/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AH060SFQ-if00-port0'

## (IP,port) tuple to send OpenPort commands to
openport_uplink_ip = ('%d.%d.%d.%d' % (0x80, 0x3b, 0xab, 0x10))
c.GroundConfiguration.openport_uplink_addresses = [(openport_uplink_ip, 30001),
                                                   (openport_uplink_ip, 30002),
                                                   (openport_uplink_ip, 30003),
                                                   (openport_uplink_ip, 30004),
                                                   (openport_uplink_ip, 30005),
                                                   (openport_uplink_ip, 30006)]

# LOS has been moved to the remote site
c.GroundConfiguration.downlink_parameters = {
    # 'los': {'baudrate': 115200, 'loop_interval': 0.2, 'port': '/dev/ttyS0'},
    'tdrss_direct': {'baudrate': 115200, 'loop_interval': 0.2,
                     'port': '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AH05KFWC-if00-port0'},
    'gse_sip': {'baudrate': 115200, 'loop_interval': 0.2,
                'port': '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A105ZADG-if00-port0'},
    'openport': {'baudrate': None, 'loop_interval': 1.0, 'port': 4502}}

c.GSEReceiverManager.downlinks_to_use = ['openport', 'gse_sip', 'tdrss_direct']


## 
c.GroundConfiguration.root_data_path = b'/data/gse_data'

# ------------------------------------------------------------------------------
# CommandSender(GroundConfiguration) configuration
# ------------------------------------------------------------------------------

## Timeout for serial command port. This sets how much time is allocated for the
#  GSE to acknowledge the command we sent.
# c.CommandSender.command_port_response_timeout = 3.0
