import struct


# These packets will be sent from the SIP to the science computer.
# Note that the '<' symbol denotes little-endian-ness


def construct_gps_position_packet(longitude, latitude, altitude, satellite_status):
    # longtidue, latitude, altitude are 4-byte IEEEstd 754 single-precision rela-format numbers
    # long and lat are in degrees, alt is in meters.
    # All are little-endian
    # Status is a single byte.
    return struct.pack('<2B3f2B', 0x10, 0x10, longitude, latitude, altitude, satellite_status, 0x03)


def construct_gps_time_packet(time_week, week_number, gps_time_offset, cpu_time):
    return struct.pack('<2B1f1h2f1B', 0x10, 0x11, time_week, week_number,
                       gps_time_offset, cpu_time, 0x03)
    # Assumed that cpu_time is a 4 byte real number like time of week and gps_time_offset
    # However the manual doesn't explicity say what type it is.


def construct_mks_pressure_altitude_packet(high, mid, low):
    return struct.pack('<2B3h1B', 0x10, 0x12, high, mid, low, 0x03)


def construct_science_request_packet():
    # test
    return struct.pack('<3B', 0x10, 0x13, 0x03)


def construct_science_command_packet(which, command):
    format_string = '<2B1B%ds1B' % len(command)
    return struct.pack(format_string, 0x10, 0x14, which, command, 0x03)


def tentative_construct_science_command_packet(which, command, value):
    # Let which be the camera number
    # command be the command string we actually want to pass.
    return construct_science_command_packet(which + command + value)
