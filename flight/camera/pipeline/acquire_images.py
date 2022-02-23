import logging
import multiprocessing as mp
import os
import time

import errno
import numpy as np
from queue import Empty as EmptyException
from traitlets import (Bool, Int, List, Unicode,Tuple, Bytes)

from pmc_turbo.utils.error_counter import CounterCollection
from pmc_turbo.utils.configuration import GlobalConfiguration
from pmc_turbo.camera.pycamera.dtypes import frame_info_dtype

logger = logging.getLogger(__name__)
import Pyro4

Pyro4.config.SERVERTYPE = 'multiplex'
Pyro4.config.SERIALIZERS_ACCEPTED = {'pickle', 'json'}
Pyro4.config.SERIALIZER = 'pickle'


camera_status_columns = ["total_frames", "camera_timestamp_offset", "main_temperature", "sensor_temperature",
                         "trigger_interval",
                         "AcquisitionFrameCount", "AcquisitionFrameRateAbs", "AcquisitionFrameRateLimit",
                         "AcquisitionMode", "ChunkModeActive",
                         "DeviceTemperature", "DeviceTemperatureSelector", "EFLensFStopCurrent",
                         "EFLensFStopMax", "EFLensFStopMin", "EFLensFStopStepSize",
                         "EFLensFocusCurrent", "EFLensFocusMax", "EFLensFocusMin", "EFLensFocusSwitch", "EFLensID",
                         "EFLensLastError", "EFLensState",
                         "ExposureAuto", "ExposureAutoAdjustTol", "ExposureAutoAlg", "ExposureAutoMax",
                         "ExposureAutoMin",
                         "ExposureAutoOutliers", "ExposureAutoRate", "ExposureAutoTarget", "ExposureMode",
                         "ExposureTimeAbs",
                         "Gain", "GainAuto", "GevTimestampValue", "PixelFormat", "PtpAcquisitionGateTime",
                         "PtpMode", "PtpStatus",
                         "StatFrameDelivered", "StatFrameDropped", "StatFrameRate", "StatFrameRescued",
                         "StatFrameShoved", "StatFrameUnderrun", "StatLocalRate", "StatPacketErrors",
                         "StatPacketMissed",
                         "StatPacketReceived", "StatPacketRequested", "StatPacketResent", "StatTimeElapsed",
                         "StreamAnnouncedBufferCount", "StreamBytesPerSecond",
                         "StreamHoldEnable", "StreamID", "StreamType", "TriggerMode", "TriggerSource"]

def next_gate_time(last_gate_time, trigger_interval):
    integer_gate_time = int(last_gate_time)
    next_integer_gate_time = integer_gate_time + ((-integer_gate_time) % trigger_interval)
    if next_integer_gate_time == integer_gate_time:
        next_integer_gate_time = integer_gate_time + trigger_interval
    return next_integer_gate_time

class AcquireImagesProcess(GlobalConfiguration):
    use_simulated_camera = Bool(False).tag(config=True)
    camera_housekeeping_subdir = Unicode('camera').tag(config=True)
    acquire_counters_name = Unicode('acquire_images').tag(config=True)
    camera_ip_address = Bytes("10.0.0.2").tag(config=True)
    trigger_interval = Int(default_value=2,min=1).tag(config=True)
    auto_reset_on_bad_focus = Bool(default_value=False).tag(config=True)
    required_camera_configuration = List(trait=Tuple(Bytes(), Bytes()),
                                        default_value=[("PtpMode", "Slave"),
                                                       ("ChunkModeActive", "1"),
                                                       ("AcquisitionFrameCount", "1"),
                                                       ('AcquisitionMode', "MultiFrame"),
                                                       ("StreamFrameRateConstrain", "0"),
                                                       ('TriggerSource', 'FixedRate'),]).tag(config=True)
    initial_camera_configuration = List(trait=Tuple(Bytes(), Bytes()),
                                        default_value=[("AcquisitionFrameCount", "1"),
                                                       ('AcquisitionFrameRateAbs', "1.3"),
                                                       ('ExposureTimeAbs', "100000"),
                                                       ('EFLensFocusCurrent', "2050")]).tag(config=True)

    def __init__(self, raw_image_buffers, acquire_image_output_queue, acquire_image_input_queue,
                 command_queue, command_result_queue, info_buffer, status, uri, **kwargs):
        super(AcquireImagesProcess,self).__init__(**kwargs)
        self.data_buffers = raw_image_buffers
        self.input_queue = acquire_image_input_queue
        self.output_queue = acquire_image_output_queue
        self.command_queue = command_queue
        self.command_result_queue = command_result_queue
        self.info_buffer = info_buffer
        self.uri = uri
        self.camera_housekeeping_dir = os.path.join(self.housekeeping_dir,self.camera_housekeeping_subdir)
        self.status = status
        self.status.value = "starting"
        self.status_log_filename = None
        self.status_log_file = None
        self.status_log_last_update = 0
        self.status_log_update_interval = 10
        self.columns = camera_status_columns
        self.child = mp.Process(target=self.run)
        # self.child.start()

    def create_log_file(self, columns):
        try:
            os.makedirs(self.camera_housekeeping_dir)
        except OSError as e:
            if e.errno == errno.EEXIST and os.path.isdir(self.camera_housekeeping_dir):
                pass
            else:
                logger.exception("Could not create housekeeping directory %s" % self.camera_housekeeping_dir)

        self.status_log_filename = os.path.join(self.camera_housekeeping_dir, (time.strftime('%Y-%m-%d_%H%M%S.csv')))
        self.status_log_file = open(self.status_log_filename, 'a')
        self.status_log_file.write('# %s %s %s %s\n' %
                                   (self.pc.get_parameter("DeviceModelName"),
                                    self.pc.get_parameter("DeviceID"),
                                    self.pc.get_parameter("DeviceFirmwareVersion"),
                                    self.pc.get_parameter("GevDeviceMACAddress")))
        self.status_log_file.write(','.join(['epoch'] + columns) + '\n')

    def get_temperatures(self):
        self.pc.set_parameter("DeviceTemperatureSelector", "Main")
        main = self.pc.get_parameter("DeviceTemperature")
        self.pc.set_parameter("DeviceTemperatureSelector", "Sensor")
        sensor = self.pc.get_parameter("DeviceTemperature")
        return dict(main_temperature=main, sensor_temperature=sensor)

    def log_status(self, status_update):
        if time.time() - self.status_log_last_update < self.status_log_update_interval:
            return
        self.status_log_last_update = time.time()
        status_update = status_update.copy()
        camera_status = status_update.pop('all_camera_parameters')
        status_update.update(camera_status)
        if self.status_log_file is None:
            self.create_log_file(self.columns)
        values = [status_update['camera_status_update_at']]
        for column in self.columns:
            values.append(status_update[column])
        self.status_log_file.write(','.join(['%s' % value for value in values]) + '\n')
        self.status_log_file.flush()

    def run(self):
        self.pipeline = Pyro4.Proxy(uri=self.uri)
        self.pipeline._pyroTimeout = 0
        self.counters = CounterCollection(self.acquire_counters_name, self.counters_dir)
        self.counters.camera_armed.reset()
        self.counters.buffer_queued.reset()
        self.counters.error_queuing_buffer.reset()
        self.counters.command_sent.reset()
        self.counters.parameter_set.reset()
        self.counters.command_non_zero_result.reset()
        self.counters.waiting_for_buffer.reset()
        self.counters.waiting_for_buffer.lazy = True # This gets incremented several times per second, so no need to record every event
        self.counters.buffer_filled.reset()
        self.counters.getting_parameters.reset()
        self.counters.waiting.reset()
        self.counters.waiting.lazy = True  # waiting gets incremented hundreds of times per second, no need to record every increment

        # Setup
        frame_number = 0
        from pmc_turbo import camera
        self.status.value = "initializing camera"
        self.pc = camera.PyCamera(self.camera_ip_address, use_simulated_camera=self.use_simulated_camera)
        for name,value in self.required_camera_configuration:
            self.pc.set_parameter(name,value)
        for name,value in self.initial_camera_configuration:
            self.pc.set_parameter(name,value)

        self.payload_size = int(self.pc.get_parameter('PayloadSize'))
        logger.info("payload size: %d" % self.payload_size)

        self.pc._pc.start_capture()

        camera_parameters_last_updated = 0

        last_trigger = int(time.time() + 1)
        buffers_on_camera = set()
        self.acquisition_start_time = time.time()
        # Run loop
        exit_request = False
        self.status.value = "idle"

        while True:
            while True:
                try:
                    ready_to_queue = self.input_queue.get_nowait()
                except EmptyException:
                    break
                if ready_to_queue is None:
                    exit_request = True
                    break
                self.status.value = "queueing buffer %d" % ready_to_queue
                image_buffer = np.frombuffer(self.data_buffers[ready_to_queue].get_obj(), dtype='uint8')
                # cast the buffer array using the compound data type that has a spot for each info field
                npy_info_buffer = np.frombuffer(self.info_buffer[ready_to_queue].get_obj(), dtype=frame_info_dtype)
                result = self.pc._pc.queue_buffer(image_buffer, npy_info_buffer)
                if result != 0:
                    logger.error("Errorcode while queueing buffer: %r" % result)
                    self.counters.error_queuing_buffer.increment()
                else:
                    buffers_on_camera.add(ready_to_queue)
                    self.counters.buffer_queued.increment()
            if exit_request:
                break
            if time.time() > last_trigger + (self.trigger_interval-0.5):
                gate_time = next_gate_time(last_trigger, self.trigger_interval)
                if not self.command_queue.empty():
                    name, value, tag = self.command_queue.get()
                    self.status.value = "sending command"
                    if name == 'trigger_interval':
                        try:
                            self.trigger_interval = int(value)
                            result = 0
                        except Exception:
                            logger.exception("Failed to set trigger_interval to %r" % value)
                            result = -1
                    else:
                        if value is None:
                            result = self.pc.run_feature_command(name)
                            self.counters.command_sent.increment()
                        else:
                            result = self.pc.set_parameter(name, value)
                            self.counters.parameter_set.increment()
                    if result:
                        logger.error("Errorcode %r while executing command %s:%r" % (result, name, value))
                        self.counters.command_non_zero_result.increment()
                    gate_time = next_gate_time(last_trigger, self.trigger_interval) # update gate time in case some time
                    # has elapsed while executing command
                    self.command_result_queue.put((tag, name, value, result, gate_time))
                self.status.value = "arming camera"
                self.pc.set_parameter('PtpAcquisitionGateTime', str(int(gate_time * 1e9)))
                time.sleep(0.1)
                self.pc.run_feature_command("AcquisitionStart")
                last_trigger = gate_time
                self.counters.camera_armed.increment()

            if not buffers_on_camera:
                self.status.value = "waiting for buffer on camera"
                time.sleep(0.001)
                self.counters.waiting_for_buffer.increment()
            else:
                self.status.value = "checking buffers"
            num_buffers_filled = 0
            for buffer_id in list(buffers_on_camera):
                npy_info_buffer = np.frombuffer(self.info_buffer[buffer_id].get_obj(), dtype=frame_info_dtype)
                if npy_info_buffer[0]['is_filled']:
                    self.status.value = 'buffer %d was filled by camera' % buffer_id
                    logger.debug(self.status.value)
                    self.output_queue.put(buffer_id)
                    buffers_on_camera.remove(buffer_id)
                    frame_number += 1
                    num_buffers_filled += 1
                    self.counters.buffer_filled.increment()
            if num_buffers_filled == 0:
                self.status.value = "waiting for buffer to be filled"
                update_at = time.time()
                if update_at - camera_parameters_last_updated > 1.0:
                    self.status.value = "getting camera parameters"
                    status = self.pc.get_all_parameters()
                    temperatures = self.get_temperatures()
                    camera_parameters_last_updated = update_at

                    self.status.value = "updating status"
                    timestamp_comparison = self.pc.compare_timestamps() * 1e6
                    status_update = dict(all_camera_parameters=status,
                                         camera_status_update_at=update_at,
                                         camera_timestamp_offset=timestamp_comparison,
                                         total_frames=frame_number,
                                         trigger_interval=self.trigger_interval,
                                         )
                    status_update.update(temperatures)
                    self.log_status(status_update)
                    self.pipeline.update_status(status_update)
                    self.counters.getting_parameters.increment()
                    if self.auto_reset_on_bad_focus:
                        focus = status['EFLensFocusCurrent']
                        focus_max = status['EFLensFocusMax']
                        focus_is_bad = False
                        try:
                            focus = int(focus)
                            focus_max = int(focus_max)
                            if focus <= 0 or focus > focus_max:
                                logger.warning("Current focus %d is bad because it is out of range: 0 to %d" % (focus, focus_max))
                                focus_is_bad = True
                        except Exception:
                            logger.exception("Focus is bad because it is not an integer %r focus_max %r" % (focus,focus_max))
                            focus_is_bad = True
                        if focus_is_bad:
                            logger.error("focus value is invalid, resetting to initial configuration")
                            for name,value in self.initial_camera_configuration:
                                self.pc.set_parameter(name,value)

                else:
                    time.sleep(0.001)
                    self.status.value = "waiting"
                    self.counters.waiting.increment()
        # if we get here, we were kindly asked to exit
        self.status.value = "exiting"
        if self.use_simulated_camera:
            self.pc._pc.quit()
        return None
