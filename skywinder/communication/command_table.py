import logging

logger = logging.getLogger(__name__)
from skywinder.communication.command_classes import Command, ListArgumentCommand, CommandManager, StringArgumentCommand

DESTINATION_ALL_CAMERAS = 255
DESTINATION_WIDEFIELD_CAMERAS = 254
DESTINATION_NARROWFIELD_CAMERAS = 253
DESTINATION_LIDAR = 252
DESTINATION_SUPER_COMMAND = 251 # use for sending commands to anyone listening, i.e for manually assigning leader
DESTINATION_LEADER = 250

def destination_to_string(destination):
    if destination < 8:
        return 'cam %d' % destination
    if destination == DESTINATION_ALL_CAMERAS:
        return 'all cameras'
    if destination == DESTINATION_WIDEFIELD_CAMERAS:
        return 'widefield'
    if destination == DESTINATION_NARROWFIELD_CAMERAS:
        return 'narrowfield'
    if destination == DESTINATION_LIDAR:
        return 'lidar'
    if destination == DESTINATION_SUPER_COMMAND:
        return 'super'
    if destination == DESTINATION_LEADER:
        return 'leader'
    return "unknown: %d" % destination

USE_BULLY_ELECTION = 254

##################################################################################################
# The following command names (firststring argument to Command) correspond to methods defined in Communicator
# Cannot alter or remove these commands without also propagating the change to the Communicator class methods.
# DISCUSS WITH GROUP BEFORE CHANGING COMMANDS

command_manager = CommandManager()
command_manager.add_command(Command("set_focus", [("focus_step", 'H')]))
command_manager.add_command(Command("set_exposure", [("exposure_time_us", 'I')]))
command_manager.add_command(Command("set_fstop", [("fstop", 'f')]))
command_manager.add_command(Command("run_focus_sweep", [('request_id', 'I'),
                                                        ('row_offset', 'H'),
                                                        ('column_offset', 'H'),
                                                        ('num_rows', 'H'),
                                                        ('num_columns', 'H'),
                                                        ('scale_by', 'f'),
                                                        ('quality', 'B'),
                                                        ('start', 'H'),
                                                        ('stop', 'H'),
                                                        ('step', 'h')]))
command_manager.add_command(StringArgumentCommand("send_arbitrary_camera_command",[("command", "s")],
                                                  docstring="Set an arbitrary camera parameter or execute a camera command.\n"
                                                            "The `command` string must be of the format <parameter name>:<parameter value> (colon delimeter)\n"
                                                            "Or, to execute a command, use the format <command name>:None"))
command_manager.add_command(Command("set_standard_image_parameters", [("row_offset", "H"),
                                                                      ("column_offset", "H"),
                                                                      ("num_rows", "H"),
                                                                      ("num_columns", "H"),
                                                                      ("scale_by", "f"),
                                                                      ("quality", "B")]))
command_manager.add_command(Command("request_specific_images", [("timestamp", "d"),
                                                                ("request_id", "I"),
                                                                ("num_images", "H"),
                                                                ("step", "i"),
                                                                ("row_offset", "H"),
                                                                ("column_offset", "H"),
                                                                ("num_rows", "H"),
                                                                ("num_columns", "H"),
                                                                ("scale_by", "f"),
                                                                ("quality", "B")]))
command_manager.add_command(ListArgumentCommand("set_peer_polling_order", 'B',
                                                docstring="Argument is list of uint8 indicating order"))
command_manager.add_command(StringArgumentCommand("request_specific_file", [("max_num_bytes", 'i'),
                                                                            ("request_id", 'I'),
                                                                            ("filename", "s")]))
command_manager.add_command(StringArgumentCommand("run_shell_command", [("max_num_bytes_returned", 'I'),
                                                                        ("request_id", 'I'),
                                                                        ("timeout", "f"),
                                                                        ("command_line", "s")],
                                                  docstring="`timeout` is maximum number of seconds command will be allowed to run.\n"
                                                            "`command_line` is shell command to execute"))
command_manager.add_command(Command("get_status_report", [("compress", "B"),
                                                          ("request_id", 'I')],
                                    docstring="if LSB of`compress` is non-zero, result will be compressed for downlink\n"
                                              "if `compress` & 0x02 is true, pipeline status will be excluded\n"
                                              "  compress=0 : include pipeline status and don't compress (results in largest file)\n"
                                              "  compress=1 : include pipeline status and compress the file for downlink\n"
                                              "  compress=2 : don't include pipeline status and don't compress\n"
                                              "  compress=3 : don't include pipeline status and compress (results in the smallest file)"))
command_manager.add_command(Command("flush_downlink_queues", []))
command_manager.add_command(Command("use_synchronized_images", [("synchronize", "B")],
                                    docstring="non-zero argument means images should be synchronized"))
command_manager.add_command(Command("set_downlink_bandwidth", [("openport", "I"),
                                                               ("highrate", "I"),
                                                               ("los", "I")],
                                    docstring="bandwidths are specified in bytes per second"))
command_manager.add_command(Command("set_leader", [("leader_id", "B")],
                                    docstring="Set leader or election directly.\n"
                                    "Typically used with destination SUPER_COMMAND to override"
                                    ))
command_manager.add_command(Command("get_command_history", [("request_id", "I"),
                                                            ("max_entries", "B")],
                                    docstring="max_entries = 0 --> return all entries"))
command_manager.add_command(Command("enable_auto_exposure",[("enabled", "B")]))
command_manager.add_command(Command("set_auto_exposure_parameters",
                                    [("max_percentile_threshold_fraction","f"),
                                     ("min_peak_threshold_fraction","f"),
                                     ("min_percentile_threshold_fraction","f"),
                                     ("adjustment_step_size_fraction","f"),
                                     ("min_exposure","I"),
                                     ("max_exposure","I")],
                                    docstring="`min_exposure` and `max_exposure` are in microseconds"))
command_manager.add_command(Command("request_blobs_by_timestamp",
                                    [("timestamp", "d"),
                                     ("request_id", "I"),
                                     ("num_images", "H"),
                                     ("step", "i"),
                                     ("stamp_size", "H"),
                                     ("blob_threshold", "f"),
                                     ("kernel_sigma", "f"),
                                     ("kernel_size", "B"),
                                     ("cell_size","H"),
                                     ("max_num_blobs", "H"),
                                     ("quality","B")]))

command_manager.add_command(Command("set_trigger_interval",
                                    [("interval", "B")]))

command_manager.add_command(StringArgumentCommand("send_lidar_command",[('command','s')]))

command_manager.add_command(Command("set_max_lidar_files_per_poll",
                                    [("max_files", "B")]))

command_manager.add_command(Command("flush_lidar_data_backlog",[]))


# add command to set pyro comm timeout?

logger.debug("Built command manager with %d total commands" % (command_manager.total_commands))


