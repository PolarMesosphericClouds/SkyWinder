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

from pmc_turbo.camera.star_finding.blobs import BlobFinder
from pmc_turbo.camera.image_processing.blosc_file import load_blosc_image
from pmc_turbo.camera.image_processing.jpeg import simple_jpeg
from pmc_turbo.camera.image_processing.hot_pixels import HotPixelMasker
from pmc_turbo.camera.pipeline.indexer import MergedIndex
from pmc_turbo.camera.pipeline.write_images import index_keys
from pmc_turbo.camera.pipeline import exposure_manager
from pmc_turbo.camera.pycamera.dtypes import image_dimensions
from pmc_turbo.communication import file_format_classes
from pmc_turbo.communication.file_format_classes import DEFAULT_REQUEST_ID
from pmc_turbo.utils.camera_id import get_camera_id
from pmc_turbo.utils.configuration import GlobalConfiguration, camera_data_dir
from pmc_turbo.utils.error_counter import CounterCollection
from pmc_turbo.utils.housekeeping_logger import HousekeepingLogger

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

        self.exposure_manager = exposure_manager.ExposureManager(parent=self)
        self.exposure_manager_logger = HousekeepingLogger(columns=self.exposure_manager.columns,
                                                          formats = ['%f' for _ in self.exposure_manager.columns],
                                                          housekeeping_dir=os.path.join(self.housekeeping_dir, 'autoexposure'))
        self.exposure_manager_logger.create_log_file()
        # Write initial parameters to ensure log file has at least one entry
        self.set_auto_exposure_parameters(max_percentile_threshold_fraction=self.exposure_manager.max_percentile_threshold_fraction,
                                          min_peak_threshold_fraction=self.exposure_manager.min_peak_threshold_fraction,
                                          min_percentile_threshold_fraction=self.exposure_manager.min_percentile_threshold_fraction,
                                          adjustment_step_size_fraction=self.exposure_manager.adjustment_step_size_fraction,
                                          min_exposure=self.exposure_manager.min_exposure,
                                          max_exposure=self.exposure_manager.max_exposure)

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
        self.setup_hot_pixel_masker()
        self.update_current_image_dirs()
        self.set_standard_image_parameters()

    def setup_pyro_daemon(self):
        self.daemon = Pyro4.Daemon(host='0.0.0.0', port=self.controller_pyro_port)
        uri = self.daemon.register(self, "controller")
        print(uri)

    def setup_hot_pixel_masker(self):
        try:
            self.hot_pixel_filename = os.path.join(camera_data_dir, 'hot_pixels',
                                                   self.hot_pixel_file_dictionary[self.camera_id])
            hot_pixels = np.load(self.hot_pixel_filename)
        except Exception:
            logger.exception("Failed to load hot pixel file from %s, dictionary of known files %r, proceeding without" % (camera_data_dir, self.hot_pixel_file_dictionary))
            hot_pixels = []
        self.hot_pixel_masker = HotPixelMasker(hot_pixels=hot_pixels, image_shape=image_dimensions)

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

    @require_pipeline
    def set_trigger_interval(self, interval):
        tag = self.pipeline.send_camera_command("trigger_interval", str(interval))
        logger.info("Set trigger interval to %s" % interval)
        self.counters.set_trigger_interval.increment()
        return tag

    @require_pipeline
    def set_focus(self, focus_step):
        tag = self.pipeline.send_camera_command("EFLensFocusCurrent", str(focus_step))
        logger.info("Set focus to %s" % focus_step)
        self.counters.set_focus.increment()
        return tag

    @require_pipeline
    def set_exposure(self, exposure_time_us):
        tag = self.pipeline.send_camera_command("ExposureTimeAbs", str(exposure_time_us))
        logger.info("Set exposure to %s us" % exposure_time_us)
        self.counters.set_exposure.increment()
        return tag

    @require_pipeline
    def set_fstop(self, fstop):
        tag = self.pipeline.send_camera_command("EFLensFStopCurrent", str(fstop))
        logger.info("Set fstop to %s" % fstop)
        self.counters.set_fstop.increment()
        return tag

    @require_pipeline
    def send_arbitrary_camera_command(self, command_string, argument_string):
        if argument_string == "None":
            argument_string = None
        tag = self.pipeline.send_camera_command(command_string, argument_string)
        logger.info("Set camera parameter %s to %r" % (command_string, argument_string))
        self.counters.send_arbitrary_command.increment()
        return tag

    @require_pipeline
    def run_focus_sweep(self, request_params, start=1950, stop=2150, step=10):
        logger.info("Running focus sweep with start=%d, stop=%d, step=%d, request_params=%r" % (start, stop, step,
                                                                                                request_params))
        focus_steps = list(range(start, stop, step))
        tags = [self.set_focus(focus_step) for focus_step in focus_steps]
        for tag in tags:
            self.outstanding_command_tags[tag] = request_params
        self.counters.run_focus_sweep.increment()

    @require_pipeline
    def get_pipeline_status(self):
        return self.pipeline.get_status()

    @require_pipeline
    def check_for_completed_commands(self):
        logger.debug("Number of outstanding commmand tags %d, Number of completed command tags %d" % (len(self.outstanding_command_tags),
                                                                                                      len(self.completed_command_tags)))
        for tag in list(self.outstanding_command_tags.keys()):
            try:
                logger.debug("Trying to get command result for tag %f" % tag)
                name, value, result, gate_time = self.pipeline.get_camera_command_result(tag)
                logger.debug("Command %s:%s completed with gate_time %f" % (name, value, gate_time))
                self.completed_command_tags[tag] = (name, value, result, gate_time)
            except KeyError:
                pass
        if self.completed_command_tags:
            for tag in list(self.completed_command_tags.keys()):
                name, value, result, gate_time = self.completed_command_tags[tag]
                index = self.merged_index.get_index_of_timestamp(gate_time)  # this will update the merged index
                if index is None:
                    self.counters.no_index_available.increment()
                    logger.warning("No index available, is the pipeline writing? Looking for gate_time %d" % gate_time)
                    self.update_current_image_dirs()
                    continue
                if index == len(self.merged_index.df):
                    self.counters.command_complete_waiting_for_image_data.increment()
                    logger.info(
                        "Command tag %f - %s:%s complete, but image data not yet available" % (tag, name, value))
                    self.update_current_image_dirs()
                    continue
                row = self.merged_index.df.iloc[index]
                timestamp = row.frame_timestamp_ns / 1e9
                if abs(gate_time - timestamp) > self.gate_time_error_threshold:
                    self.counters.gate_time_threshold_error.increment()
                    logger.warning("Command tag %f - %s:%s complete, but image timestamp %f does not match "
                                   "gate_timestamp %f to within specified threshold %f. Is something wrong with PTP?"
                                   % (tag, name, value, gate_time, timestamp, self.gate_time_error_threshold))
                request_params = self.outstanding_command_tags.pop(tag)
                _ = self.completed_command_tags.pop(tag)
                logger.info("Command tag %f - %s:%s retired" % (tag, name, value))
                logger.debug("Command %s:%s with request_params %r retired by image %r" % (name, value,
                                                                                           request_params, dict(row)))
                self.request_image_by_index(index, **request_params)
        else:
            logger.debug("Forcing update of index because no commands have been executed recently")
            self.update_current_image_dirs()
        if self.auto_exposure_enabled:
            logger.debug("Checking exposure")
            self.auto_exposure()

    def update_current_image_dirs(self):
        if self.merged_index is None or self.merged_index.df is None:
            self.merged_index = MergedIndex('*', data_dirs=self.data_directories)
        self.merged_index.update()

    def auto_exposure(self):
        try:
            new_exposure = self.exposure_manager.check_exposure(self.get_pipeline_status(), self.get_latest_fileinfo())
            if new_exposure is not None:
                self.set_exposure(int(new_exposure))
        except Exception:
            logger.exception("Auto exposure failed")

    def enable_auto_exposure(self, enabled):
        if enabled:
            self.auto_exposure_enabled = True
            logger.info("Enabling auto exposure")
        else:
            self.auto_exposure_enabled = False
            logger.info("Disabling auto exposure")

    def is_auto_exposure_enabled(self):
        return self.auto_exposure_enabled

    def set_auto_exposure_parameters(self, max_percentile_threshold_fraction,
                                     min_peak_threshold_fraction,
                                     min_percentile_threshold_fraction,
                                     adjustment_step_size_fraction,
                                     min_exposure,
                                     max_exposure):
        self.exposure_manager.min_peak_threshold_fraction = min_peak_threshold_fraction
        self.exposure_manager.max_percentile_threshold_fraction = max_percentile_threshold_fraction
        self.exposure_manager.min_exposure = min_exposure
        self.exposure_manager.max_exposure = max_exposure
        self.exposure_manager.adjustment_step_size_fraction = adjustment_step_size_fraction
        self.exposure_manager.min_percentile_threshold_fraction = min_percentile_threshold_fraction
        self.exposure_manager_logger.write_log_entry(data=dict(epoch=time.time(),
                                                               min_peak_threshold_fraction=min_peak_threshold_fraction,
                                                               max_percentile_threshold_fraction=max_percentile_threshold_fraction,
                                                               min_percentile_threshold_fraction=min_percentile_threshold_fraction,
                                                               min_exposure=min_exposure, max_exposure=max_exposure,
                                                               adjustment_step_size_fraction=adjustment_step_size_fraction))

    def get_latest_fileinfo(self):
        if self.merged_index is None:
            self.update_current_image_dirs()
        if self.merged_index is not None:
            result = self.merged_index.get_latest(update=False)  # updating the index is done in the main loop
            if result is None:
                raise RuntimeError("No candidates for latest file!")
            else:
                return result
        else:
            raise RuntimeError("No candidates for latest file!")

    def get_latest_standard_image(self):
        params = self.standard_image_parameters.copy()
        file_obj = self.get_latest_jpeg(**params)
        return file_obj

    def get_latest_jpeg(self, request_id, row_offset=0, column_offset=0, num_rows=3232, num_columns=4864,
                        scale_by=1 / 8., **kwargs):
        info = self.get_latest_fileinfo()
        return self.get_image_by_info(info, request_id=request_id, row_offset=row_offset, column_offset=column_offset,
                                      num_rows=num_rows, num_columns=num_columns, scale_by=scale_by,
                                      **kwargs)

    def set_standard_image_parameters(self, row_offset=0, column_offset=0, num_rows=3232, num_columns=4864,
                                      scale_by=1 / 8., quality=75, format='jpeg'):
        self.standard_image_parameters = dict(row_offset=row_offset, column_offset=column_offset,
                                              num_rows=num_rows, num_columns=num_columns,
                                              scale_by=scale_by,
                                              quality=quality,
                                              format=format, request_id=DEFAULT_REQUEST_ID)

    def request_image_by_index(self, index, **kwargs):
        """

        Parameters
        ----------
        index

        Required kwargs
        ---------------
        request_id

        """
        self.merged_index.update()
        index_row_data = dict(self.merged_index.df.iloc[index])
        self.downlink_queue.append(self.get_image_by_info(index_row_data, **kwargs).to_buffer())

    def request_specific_images(self, timestamp, request_id, num_images=1, row_offset=0, column_offset=0,
                                num_rows=3232, num_columns=4864, scale_by=1 / 8., quality=75, format='jpeg', step=-1):
        selection = self.timestamp_selection(num_images, step, timestamp)
        for _, index_row in selection.iterrows():
            self.downlink_queue.append(self.get_image_by_info(index_row, row_offset=row_offset,
                                                              column_offset=column_offset,
                                                              num_rows=num_rows, num_columns=num_columns,
                                                              scale_by=scale_by, quality=quality, format=format,
                                                              request_id=request_id).to_buffer())

    def timestamp_selection(self, num_images, step, timestamp):
        last_index = self.merged_index.get_index_of_timestamp(timestamp)
        if last_index is None:
            raise RuntimeError("No index available!")
        first_index = last_index + step * num_images
        if first_index < 0:
            logger.warning("request timestamp %f, num_images %d, step %d resulted in negative first index: %d, forcing it to 0"
                     % (timestamp, num_images, step, first_index))
            first_index = 0

        logger.debug("request timestamp %f, num_images %d, step %d -> first index: %d, last index: %d, total rows: %d"
                     % (timestamp, num_images, step, first_index, last_index, self.merged_index.df.shape[0]))
        if first_index > last_index:
            first_index, last_index = last_index, first_index
        selection = self.merged_index.df.iloc[first_index:last_index:abs(step)]
        logger.debug("selected %d rows" % selection.shape[0])
        if selection.shape[0] == 0:
            raise ValueError("Zero images match the selection parameters. Check that 'step' has the correct sign.")
        return selection

    def request_blobs_by_timestamp(self, timestamp, request_id, num_images, step, stamp_size,
                                   blob_threshold, kernel_sigma, kernel_size, cell_size, max_num_blobs,
                                   quality=75, format='jpeg'):
        selection = self.timestamp_selection(num_images, step, timestamp)
        for _, index_row in selection.iterrows():
            blob_images = self.get_blobs_by_info(index_row=index_row, request_id=request_id, stamp_size=stamp_size,
                                                 blob_threshold=blob_threshold, kernel_sigma=kernel_sigma,
                                                 kernel_size=kernel_size, cell_size=cell_size,
                                                 max_num_blobs=max_num_blobs, quality=quality, format=format)
            for blob_image in blob_images:
                self.downlink_queue.append(blob_image.to_buffer())

    def get_blobs_by_info(self, index_row, request_id, stamp_size,
                          blob_threshold, kernel_sigma, kernel_size, cell_size, max_num_blobs,
                          quality=75, format='jpeg'):
        image, chunk = load_blosc_image(index_row['filename'])
        tic = time.time()
        image = self.hot_pixel_masker.process(image)
        blob_finder = BlobFinder(image, blob_threshold=blob_threshold, kernel_size=kernel_size,
                                 kernel_sigma=kernel_sigma,
                                 cell_size=cell_size, fit_blobs=False)
        logger.debug("Found %d blobs in %.2f seconds" % (len(blob_finder.blobs), (time.time() - tic)))
        results = []
        for blob in blob_finder.blobs:
            if len(results) >= max_num_blobs:
                break
            row_offset = blob.x - stamp_size // 2
            column_offset = blob.y - stamp_size // 2
            stamp = image[row_offset:row_offset + stamp_size, column_offset:column_offset + stamp_size]
            if stamp.size == 0:  # the blob was too close to an edge of the image, so don't bother returning it
                logger.debug("Skipping blob at (%d,%d) because it is too close to edge of image" % (blob.x, blob.y))
                continue
            results.append(self.make_image_file(stamp, index_row_data=index_row, request_id=request_id,
                                                row_offset=row_offset, column_offset=column_offset,
                                                num_rows=stamp.shape[0], num_columns=stamp.shape[1], scale_by=1,
                                                quality=quality, format=format))
        return results

    def request_standard_image_at(self, timestamp):
        # use step=1 to ensure that we get the image closest to timestamp. Otherwise we'd get the image immediately before
        self.request_specific_images(timestamp, step=1, **self.standard_image_parameters)

    def get_image_by_info(self, index_row_data, request_id, row_offset=0, column_offset=0, num_rows=3232,
                          num_columns=4864, scale_by=1 / 8., quality=75, format='jpeg'):
        image, chunk = load_blosc_image(index_row_data['filename'])
        image = self.hot_pixel_masker.process(image)
        image = image[row_offset:row_offset + num_rows + 1, column_offset:column_offset + num_columns + 1]
        return self.make_image_file(image, index_row_data=index_row_data, request_id=request_id, row_offset=row_offset,
                                    column_offset=column_offset, num_rows=num_rows, num_columns=num_columns,
                                    scale_by=scale_by,
                                    quality=quality, format=format)

    def make_image_file(self, image, index_row_data, request_id, row_offset, column_offset, num_rows, num_columns,
                        scale_by, quality, format):
        params = dict()
        for key in index_keys:
            if key == 'filename':
                continue
            params[key] = index_row_data[key]
        params['camera_id'] = self.camera_id
        params['request_id'] = request_id
        params['row_offset'] = row_offset
        params['column_offset'] = column_offset
        params['num_rows'] = num_rows
        params['num_columns'] = num_columns
        params['scale_by'] = scale_by
        params['quality'] = quality
        if format == 'jpeg':
            payload, offset, scale = simple_jpeg(image, scale_by=scale_by, quality=quality)
            params['pixel_scale'] = scale
            params['pixel_offset'] = offset
            file_obj = file_format_classes.JPEGFile(payload=payload, **params)
        else:
            raise ValueError("Unsupported format requested %r" % format)
        return file_obj

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

    def run_shell_command(self, command_line, max_num_bytes_returned, request_id, timeout):
        timestamp = time.time()
        # preexec_fn allows the process to be killed if needed, see http://stackoverflow.com/a/4791612
        # Using stderr=subprocess.PIPE will fail for more than 64 KB of output, see:
        #  https://thraxil.org/users/anders/posts/2008/03/13/Subprocess-Hanging-PIPE-is-your-enemy/
        stderr_file = tempfile.TemporaryFile()
        stdout_file = tempfile.TemporaryFile()
        proc = subprocess.Popen(command_line, shell=True, stderr=stderr_file, stdout=stdout_file,
                                preexec_fn=os.setsid)
        while time.time() - timestamp < timeout:
            returncode = proc.poll()
            if returncode is not None:
                proc.communicate()
                stderr_file.seek(0)
                stderr = stderr_file.read()
                stdout_file.seek(0)
                stdout = stdout_file.read()
                if len(stdout) > max_num_bytes_returned:
                    stdout = stdout[:max_num_bytes_returned]
                stderr_bytes = max_num_bytes_returned - len(stdout)
                if stderr_bytes > 0:
                    stderr_return = stderr[:stderr_bytes]
                else:
                    stderr_return = ''
                payload = "RETURNCODE: %d\nSTDOUT\n%s\nSTDERR\n%s\n" % (returncode, stdout, stderr_return)
                file_object = file_format_classes.ShellCommandFile(payload=payload,
                                                                   returncode=returncode,
                                                                   timestamp=timestamp,
                                                                   timed_out=0,
                                                                   request_id=request_id,
                                                                   camera_id=self.camera_id)
                self.downlink_queue.append(file_object.to_buffer())
                return
            time.sleep(0.1)

        logger.warning("Shell command '%r' failed to complete before timeout and will be killed" % command_line)
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except OSError:
            logger.exception("Failed to kill command %r" % command_line)
        returncode = proc.wait()
        proc.communicate()
        stderr_file.seek(0)
        stderr = stdout_file.read()
        stdout_file.seek(0)
        stdout = stdout_file.read()
        stderr_bytes = max_num_bytes_returned - len(stdout)
        if stderr_bytes > 0:
            stderr_return = stderr[:stderr_bytes]
        else:
            stderr_return = ''
        payload = "KILLED: STDOUT\n%s\nSTDERR\n%s\n" % (stdout, stderr_return)

        file_object = file_format_classes.ShellCommandFile(payload=payload,
                                                           returncode=returncode,
                                                           timestamp=timestamp,
                                                           timed_out=1,
                                                           request_id=request_id,
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
