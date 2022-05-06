import logging
import multiprocessing as mp
import os
import time
from Queue import Empty as EmptyException

logger = logging.getLogger(__name__)


import numpy as np

from pmc_turbo.camera.image_processing.blosc_file import write_image_blosc
from pmc_turbo.camera.pycamera.dtypes import frame_info_dtype, chunk_num_bytes, chunk_dtype
from pmc_turbo.utils.watchdog import setup_reset_watchdog

percentiles_to_compute = [0,1,10,20,30,40,50,60,70,80,90,99,100]
percentile_keys = ['percentile_%d' % k for k in percentiles_to_compute]

index_file_name = 'index.csv'
index_keys = ['file_index',
              'write_timestamp',
              'frame_timestamp_ns',
              'frame_status',
              'frame_id',
              'acquisition_count',
              'lens_status',
              'focus_step',
              'aperture_stop',
              'exposure_us',
              'gain_db',
              'focal_length_mm',
              'filename'] + percentile_keys
index_file_header = ",".join(index_keys) + '\n'

DISK_MIN_BYTES_AVAILABLE = 100*1024*1024 # 100 MiB



class WriteImageProcess(object):
    def __init__(self, input_buffers, input_queue, output_queue, info_buffer, status, output_dir,
                 available_disks, write_enable, rate_limit_interval, use_watchdog):
        self.data_buffers = input_buffers
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.info_buffer = info_buffer
        self.original_disks = available_disks
        self.available_disks = self.check_disk_space(self.original_disks)
        self.write_enable = write_enable
        self.rate_limit_interval = rate_limit_interval
        self.use_watchdog=use_watchdog
        if rate_limit_interval:
            logger.info("Rate limiting writer thread for disks %r to %d second intervals"
                        % (self.available_disks, self.rate_limit_interval))
        self.output_dirs = [os.path.join(rpath,output_dir) for rpath in self.available_disks]
        for dname in self.output_dirs:
            try:
                os.mkdir(dname)
            except OSError:
                logger.exception("Error creating data directory %s" % dname)
        self.disk_to_use = 0
        self.status = status
        if self.output_dirs:
            self.status.value = "starting"
        else:
            self.status.value = "no disk space"
            self.write_enable.value = False
        self.child = mp.Process(target=self.run)

    def check_disk_space(self,directories):
        directories_with_free_space = []
        for disk in directories:
            stats = os.statvfs(disk)
            bytes_available = stats.f_bavail*stats.f_frsize
            if bytes_available > DISK_MIN_BYTES_AVAILABLE:
                directories_with_free_space.append(disk)
            else:
                logger.warning("Insufficient disk space available on %s, only %d MiB" % (disk,bytes_available//2**20))
        return directories_with_free_space

    def run(self):
        if not self.available_disks:
            logger.warning("No disk space available on any of %s, exiting" % (' '.join(self.original_disks)))
            return
        frame_indexes = dict([(dirname,0) for dirname in self.output_dirs])
        for dirname in self.output_dirs:
            with open(os.path.join(dirname,index_file_name),'w') as fh:
                fh.write(index_file_header)
                fh.flush()
                os.fsync(fh.fileno())
        while True:
            try:
                process_me = self.input_queue.get_nowait()
            except EmptyException:
                self.status.value = "waiting"
                time.sleep(0.1)
                continue
            if process_me is None:
                self.status.value = "exiting"
                logger.info("Exiting normally")
                break
            else:
                self.status.value = "checking disk"
                self.output_dirs = self.check_disk_space(self.output_dirs)
                if not self.output_dirs:
                    self.status.value = "no disk space"
                    logger.warning("No disk space available on any of %s, exiting" % (' '.join(self.original_disks)))
                    break
                if self.disk_to_use >= len(self.output_dirs):
                    self.disk_to_use = 0
                self.status.value = "waiting for lock"
                with self.data_buffers[process_me].get_lock():
                    self.status.value = "processing %d" % process_me
                    logger.debug(self.status.value)

                    image_buffer = np.frombuffer(self.data_buffers[process_me].get_obj(), dtype='uint16')
                    npy_info_buffer = np.frombuffer(self.info_buffer[process_me].get_obj(),dtype=frame_info_dtype)
                    info = dict([(k,npy_info_buffer[0][k]) for k in frame_info_dtype.fields.keys()])
                    chunk_data = image_buffer.view('uint8')[-chunk_num_bytes:].view(chunk_dtype)[0]
                    image = image_buffer.view('uint8')[:-chunk_num_bytes].view('uint16')

                    # make filename
                    ts = time.strftime("%Y-%m-%d_%H%M%S")
                    info_str = '_'.join([('%s=%r' % (k,v)) for (k,v) in info.items()])
                    ts = ts + '_' + info_str
                    dirname = self.output_dirs[self.disk_to_use]
                    fname = os.path.join(dirname,ts)

                    lens_status = chunk_data['lens_status_focus'] >> 10
                    focus_step = chunk_data['lens_status_focus'] & 0x3FF

                    #compute some image statistics
                    self.status.value = "computing statistics"
                    percentiles = np.percentile(image[::16],percentiles_to_compute)
                    percentiles_string = ','.join([('%f' % pct) for pct in percentiles])

                    if self.write_enable.value:
                        self.status.value = "writing %d" % process_me
                        write_image_blosc(fname, image_buffer)  # write the blosc compressed image to disk

                        # add the file to the index
                        with open(os.path.join(dirname,index_file_name),'a') as fh:
                            fh.write('%d,%f,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%s,%s\n' %
                                     (frame_indexes[dirname],
                                      time.time(),
                                      info['timestamp'],
                                      info['frame_status'],
                                      info['frame_id'],
                                      chunk_data['acquisition_count'],
                                      lens_status,
                                      focus_step,
                                      chunk_data['lens_aperture'],
                                      chunk_data['exposure_us'],
                                      chunk_data['gain_db'],
                                      chunk_data['lens_focal_length'],
                                      fname,
                                      percentiles_string
                                      ))
                            fh.flush()
                            os.fsync(fh.fileno())

                        if self.use_watchdog:
                            setup_reset_watchdog()
                        if self.rate_limit_interval:
                            self.status.value = "throttling"
                            time.sleep(self.rate_limit_interval)
                    self.disk_to_use = (self.disk_to_use + 1) % len(self.output_dirs) # if this thread is cycling
                                                                                # between disks, do the cycling here.
                    frame_indexes[dirname] = frame_indexes[dirname] + 1
                    self.status.value = "finishing %d" % process_me
                    self.output_queue.put(process_me)

        self.status.value = "exiting"
        return None


