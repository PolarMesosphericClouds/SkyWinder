import subprocess
import shlex
import re
import logging
import numpy as np
logger = logging.getLogger(__name__)

TIMEOUT_ACTION_HARD_RESET = 1
TIMEOUT_ACTION_POWER_CYCLE = 3

def run_sudo_command_with_timeout(command,timeout=1):
    full_command = "sudo timeout %f %s" % (timeout, command)
    try:
        result = subprocess.check_output(shlex.split(full_command),stderr=subprocess.STDOUT)
    except (subprocess.CalledProcessError, OSError):
        logger.exception("failed to execute command %s" % full_command)
        result = None
    return result

def get_watchdog_raw_info():
    return run_sudo_command_with_timeout("bmc-watchdog --get")

def get_watchdog_info():
    result = get_watchdog_raw_info()
    if result is not None:
        return parse_watchdog_info(result) #pragma: no cover
    return np.nan, np.nan, np.nan

def parse_watchdog_info(raw_info_string):
    current_countdown_matches = re.findall("Current Countdown:\s*(\d+)",raw_info_string)
    current_countdown = np.nan
    if current_countdown_matches:
        try:
            current_countdown = int(current_countdown_matches[0])
        except ValueError: #pragma: no cover
            logger.warning("Couldn't parse raw_info_string %r" % current_countdown_matches) #pragma: no cover
    initial_countdown = np.nan
    initial_countdown_matches = re.findall("Initial Countdown:\s*(\d+)",raw_info_string)
    if initial_countdown_matches:
        try:
            initial_countdown = int(initial_countdown_matches[0])
        except ValueError: #pragma: no cover
            logger.warning("Couldn't parse raw_info_string %r" % initial_countdown_matches) #pragma: no cover
    is_running = False
    is_running_matches = re.findall("Timer:\s*(\w+)",raw_info_string)
    if is_running_matches:
        try:
            is_running = is_running_matches[0]
        except Exception: #pragma: no cover
            logger.warning("Couldn't parse raw_info_string %r" % is_running_matches) #pragma: no cover
    is_running = (is_running == "Running")
    return is_running, initial_countdown, current_countdown

def setup_reset_watchdog(start=True,timeout=600, action=TIMEOUT_ACTION_POWER_CYCLE):
    if start:
        start_argument = '-w -x'
    else:
        start_argument = ''
    return run_sudo_command_with_timeout("bmc-watchdog --set -a %d -i %d %s" % (action,timeout,start_argument))


def just_reset_watchdog():
    return run_sudo_command_with_timeout("bmc-watchdog --reset") #pragma: no cover

