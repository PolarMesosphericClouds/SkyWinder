

def get_human_readable_housekeeping_mapping(camera_items, collectd_items, labjack_items, charge_controller_items):
    return {

        # General
        'temperature':
            {
                # Camera
                'main_camera': camera_items['main_temperature'],
                'camera_sensor': camera_items['sensor_temperature'],
                'camera_device_temperature': camera_items['DeviceTemperature'],
                # Collectd
                'cpu': collectd_items["ipmi_temperature-CPU Temp processor (3.1)"],
                'board': collectd_items["ipmi_temperature-System Temp system_board (7.1)"],
                # check what collectd_items[sensors_coretemp_isa-0000_* represent

                #  labjack @ lens, labjack @ back, labjack internal sensor
                'lens_temperature': labjack_items['ain6'] * 1000,
                'wall_temp': labjack_items['ain7'] * 1000,
                'labjack_temp': labjack_items['temperature']

                # Need to add disk temperatures when hddtemp is logged.
            },
        # Camera

        'lens_status':
            {
                'current_focus_step': camera_items["EFLensFocusCurrent"],
                'min_focus_step': camera_items["EFLensFocusMin"],
                'max_focus_step': camera_items["EFLensFocusMax"]
            },
        'exposure': camera_items['ExposureTimeAbs'],
        'dropped_frames': camera_items["StatFrameDropped"],
        # Collectd
        'data_usage':
            {
                'data1_free': collectd_items["df-data1_df_complex-free"],
                'data2_free': collectd_items["df-data2_df_complex-free"],
                'data3_free': collectd_items["df-data3_df_complex-free"],
                'data4_free': collectd_items["df-data4_df_complex-free"],
                'root_free': collectd_items["df-root_df_complex-free"],
            },
        'voltage':
            {
                '12v_motherboard_input': collectd_items["ipmi_voltage-12V system_board (7.17)"]
            },
        'collectd_camera_computer_stats':
            {
                'md_disks_active': collectd_items["md-0_md_disks-active"],
                'md_disks_failed': collectd_items["md-0_md_disks-failed"],
                "memory_used": collectd_items["memory_memory-used"],
                "memory_free": collectd_items["memory_memory-free"],

            },

        # Charger controller
        # Add scaling to these values - store in constants
        'battery_voltage': charge_controller_items['register_025'],
        'array_voltage': charge_controller_items['register_028'],
        'battery_current': charge_controller_items['register_029'],
        'array_current': charge_controller_items['register_030'],
        'heatsink_temperature': charge_controller_items['register_036'],  # Is this a necessary thing?
        'battery_temperature': charge_controller_items['register_035'],
        'power_in': charge_controller_items['register_060'],
        'power_out': charge_controller_items['register_059'],

        # Labjack
        # 'pressure': labjack_items['???'], look at docs, find which input is labjack temp

    }
