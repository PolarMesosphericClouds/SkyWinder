import logging
import os
import select
import signal
import subprocess
import tempfile
import time
from functools import wraps

import numpy as np
import Pyro4
import Pyro4.errors
from traitlets import (Float, Bool, Dict)

from skywinder_streamlined_flight_control.communication import file_format_classes
from skywinder_streamlined_flight_control.communication.file_format_classes import DEFAULT_REQUEST_ID
from skywinder_streamlined_flight_control.utils.camera_id import get_camera_id
from skywinder_streamlined_flight_control.utils.configuration import GlobalConfiguration, camera_data_dir
from skywinder_streamlined_flight_control.utils.error_counter import CounterCollection

logger = logging.getLogger(__name__)


class ImageParameters(object):
    pass


def require_pipeline(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        self = args[0]
        if self.pipeline is None:
            return None
        else:
            try:
                return func(*args, **kwargs)
            except Pyro4.errors.CommunicationError as e:
                import sys
                raise type(e)(type(e)("Error communicating with pipeline!\n" + str(e))).with_traceback(sys.exc_info()[2])

    return wrapper


@Pyro4.expose
class Controller(GlobalConfiguration):
    gate_time_error_threshold = Float(2e-3, min=0).tag(config=True)
    main_loop_interval = Float(3.0, min=0).tag(config=True)
    auto_exposure_enabled = Bool(default_value=True).tag(config=True)
    hot_pixel_file_dictionary = Dict().tag(config=True)
    minimum_update_interval = Float(10.0, min=0).tag(config=True)

    def __init__(self, **kwargs):
        super(Controller, self).__init__(**kwargs)
        logger.info("Starting with configuration %r" % self.config)
        if 'pipeline' in kwargs:
            self.pipeline = kwargs['pipeline']
        else:
            self.pipeline = Pyro4.Proxy("PYRO:pipeline@0.0.0.0:%d" % int(self.pipeline_pyro_port))
        self.latest_image_subdir = ''
        self.merged_index = None
        self.downlink_queue = []
        self.outstanding_command_tags = {}
        self.completed_command_tags = {}
        self.last_update_time = 0

        self.counters = CounterCollection('controller', self.counters_dir)
        self.counters.set_focus.reset()
        self.counters.set_exposure.reset()
        self.counters.set_fstop.reset()
        self.counters.set_trigger_interval.reset()
        self.counters.send_arbitrary_command.reset()
        self.counters.run_focus_sweep.reset()

        self.counters.no_index_available.reset()
        self.counters.command_complete_waiting_for_image_data.reset()
        self.counters.gate_time_threshold_error.reset()

        self.camera_id = get_camera_id()
        #self.setup_hot_pixel_masker()
        #self.update_current_image_dirs()
        #self.set_standard_image_parameters()

    def setup_pyro_daemon(self):
        self.daemon = Pyro4.Daemon(host='0.0.0.0', port=self.controller_pyro_port)
        uri = self.daemon.register(self, "controller")
        print(uri)

    def main_loop(self):
        events, _, _ = select.select(self.daemon.sockets, [], [], self.main_loop_interval)
        if (not events) or (time.time() - self.last_update_time) > self.minimum_update_interval:
            # check_for_completed_commands also updates the merged index
            try:
                self.check_for_completed_commands()
            except Exception:
                logger.exception("Failure while checking completed commands")
            self.last_update_time = time.time()
        if events:
            logger.debug("Got %d Pyro events to process" % len(events))
            self.daemon.events(events)

    def request_specific_file(self, filename, max_num_bytes, request_id):
        timestamp = time.time()
        try:
            with open(filename, 'r') as fh:
                if max_num_bytes < 0:
                    fh.seek(max_num_bytes, os.SEEK_END)
                data = fh.read(max_num_bytes)
        except IOError as e:
            data = repr(e)
        file_object = file_format_classes.GeneralFile(payload=data,
                                                      timestamp=timestamp,
                                                      request_id=request_id,
                                                      filename=filename,
                                                      camera_id=self.camera_id)
        self.downlink_queue.append(file_object.to_buffer())

    def get_next_data_for_downlink(self):
        if self.downlink_queue:
            result = self.downlink_queue[0]
            self.downlink_queue = self.downlink_queue[1:]
            logger.debug("Sending item with length %d from queue. %d items remain in the queue" % (
                len(result), len(self.downlink_queue)))
        else:
            logger.debug("Sending latest standard image")
            result = self.get_latest_standard_image().to_buffer()
        return result

    def add_file_to_downlink_queue(self, file_buffer):
        logger.debug('File_buffer added to downlink queue: first 20 bytes are %r' % file_buffer[:20])
        self.downlink_queue.append(file_buffer)

    def flush_downlink_queue(self):
        num_items = len(self.downlink_queue)
        self.downlink_queue = []
        logger.info("Flushed %d files from downlink queue" % num_items)

    def get_downlink_queue_depth(self):
        return len(self.downlink_queue)
