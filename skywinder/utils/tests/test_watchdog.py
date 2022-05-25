from skywinder.utils.watchdog import parse_watchdog_info, get_watchdog_info
test_case_1 = """Timer Use:                   SMS/OS
Timer:                       Stopped
Logging:                     Enabled
Timeout Action:              Power Cycle
Pre-Timeout Interrupt:       None
Pre-Timeout Interval:        0 seconds
Timer Use BIOS FRB2 Flag:    Clear
Timer Use BIOS POST Flag:    Clear
Timer Use BIOS OS Load Flag: Clear
Timer Use BIOS SMS/OS Flag:  Clear
Timer Use BIOS OEM Flag:     Clear
Initial Countdown:           600 seconds
Current Countdown:           600 seconds
"""

test_case_2 = """Timer Use:                   SMS/OS
Timer:                       Running
Logging:                     Enabled
Timeout Action:              Power Cycle
Pre-Timeout Interrupt:       None
Pre-Timeout Interval:        0 seconds
Timer Use BIOS FRB2 Flag:    Clear
Timer Use BIOS POST Flag:    Clear
Timer Use BIOS OS Load Flag: Clear
Timer Use BIOS SMS/OS Flag:  Clear
Timer Use BIOS OEM Flag:     Clear
Initial Countdown:           600 seconds
Current Countdown:           598 seconds
"""

test_case_3 = """Timer Use:                   SMS/OS
Timer:                       xx
Logging:                     Enabled
Timeout Action:              Power Cycle
Pre-Timeout Interrupt:       None
Pre-Timeout Interval:        0 seconds
Timer Use BIOS FRB2 Flag:    Clear
Timer Use BIOS POST Flag:    Clear
Timer Use BIOS OS Load Flag: Clear
Timer Use BIOS SMS/OS Flag:  Clear
Timer Use BIOS OEM Flag:     Clear
Initial Countdown:           xx seconds
Current Countdown:           xx seconds
"""

def test_parse_watchdog_stopped():
    is_running, initial_countdown, current_countdown = parse_watchdog_info(test_case_1)
    assert not is_running
    assert initial_countdown == 600
    assert current_countdown == 600

def test_parse_watchdog_running():
    is_running, initial_countdown, current_countdown = parse_watchdog_info(test_case_2)
    assert is_running
    assert initial_countdown == 600
    assert current_countdown == 598

def test_parse_watchdog_corrupt():
    is_running, initial_countdown, current_countdown = parse_watchdog_info(test_case_3)
    assert not is_running
    assert initial_countdown != initial_countdown
    assert current_countdown != current_countdown

def test_get_info():
    print(get_watchdog_info())
