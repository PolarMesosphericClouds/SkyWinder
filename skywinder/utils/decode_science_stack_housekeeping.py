import struct

SCIENCE_STACK_LABELS = [
    "cam1_curr",
    "cam2_curr",
    "cam3_curr",
    "cam4_curr",
    "cam1_pres",
    "cam2_pres",
    "cam3_pres",
    "cam4_pres",
    "vbmon_p",
    "vbmon_s",
    "sscur_p1",
    "sscur_p2",
    "cam5_curr",
    "spare_p",
    "tel_p",
    "sscur_p3",
    "cam5_pres",
    "spare_p",
    "sstemp1",
    "sstemp2",
    "sstemp3",
    "sstemp4",
    "cam6_curr",
    "cam6_pres",
    "cam7_curr",
    "cam7_pres",
    "lidar_curr",
    "tel_s_curr",
    "spare_s",
    "sscur_s1",
    "sscur_s2",
    "sscur_s3"
]


def unpack_housekeeping(gse_housekeeping_payload):
    digital_bytes = struct.unpack('2B', gse_housekeeping_payload[:2])

    values_12bit = struct.unpack('253B', gse_housekeeping_payload[2:])
    return digital_bytes, values_12bit


def swap_two_nibbles(byte):
    return (byte << 4 | byte >> 4) & 255


def stitch_3_bytes(bytes):
    return (bytes[0] << 16) | (bytes[1] << 8) | (bytes[2])


def grab_front_and_back_12_bit(stitched_bytes):
    front = stitched_bytes >> 12
    back = stitched_bytes & 4095
    return front, back


def switch_first_and_last_nibble(number_12_bit):
    first_nibble = number_12_bit << 8 & 4095
    second_nibble = (((number_12_bit & 255) >> 4) << 4) & 255
    third_nibble = number_12_bit >> 8
    return first_nibble | second_nibble | third_nibble


def convert_to_float(byte):
    return byte * 5 / 4095.


def interpret_payload(gse_housekeeping_payload):
    digital, analog = unpack_housekeeping(gse_housekeeping_payload)
    swapped = []
    for byte in analog:
        swapped.append(swap_two_nibbles(byte))
    stitched = []
    for i, byte in enumerate(swapped):
        if i % 3 == 2:
            stitched.append(stitch_3_bytes(swapped[i - 2:i + 1]))
    values_12_bit = []
    for value in stitched:
        front, back = grab_front_and_back_12_bit(value)
        values_12_bit.append(front)
        values_12_bit.append(back)
    final_12_bits = []
    for value in values_12_bit:
        final_12_bits.append(switch_first_and_last_nibble(value))
    final_floats = []
    for byte in final_12_bits:
        final_floats.append(convert_to_float(byte))

    return final_floats

def pack_floats_into_dict(floats):
    housekeeping_dict ={}
    for i, label in enumerate(SCIENCE_STACK_LABELS):
        housekeeping_dict[label] = floats[i]
    return housekeeping_dict


def interpret_digital_bytes_housekeeping_payload(digital_bytes):
    digital1 = digital_bytes[0]
    # Pin 9,10,11,12,13,14,15,16
    digital2 = digital_bytes[1]
    # Pins 1,2,3,4,5,6,7,8

    # For all but lidar 0 = on, 1 = off. 8, 14, 15, 16 unused. 8 held low, 14, 15, 16 held high.

    d1 = '{0:08b}'.format(ord(digital1))
    d2 = '{0:08b}'.format(ord(digital2))

    return d2 + d1