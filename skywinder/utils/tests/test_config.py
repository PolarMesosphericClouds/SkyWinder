import os
import shutil
import tempfile

import traitlets.config.loader

from skywinder.utils.configuration import default_config_dir


class BasicTestHarness(object):
    config_file = 'no_hardware.py'

    def setup(self):
        self.basic_config = traitlets.config.loader.load_pyconfig_files([self.config_file], default_config_dir)
        disk_dirs = [tempfile.mkdtemp() for k in range(4)]
        self.basic_config.GlobalConfiguration.log_dir = tempfile.mkdtemp()

        self.basic_config.GlobalConfiguration.housekeeping_dir = os.path.join(
            self.basic_config.GlobalConfiguration.log_dir, 'housekeeping')
        self.basic_config.GlobalConfiguration.camera_commands_dir = os.path.join(
            self.basic_config.GlobalConfiguration.log_dir, 'camera_commands')
        self.basic_config.GlobalConfiguration.counters_dir = os.path.join(self.basic_config.GlobalConfiguration.log_dir,
                                                                          'counters')
        self.basic_config.GlobalConfiguration.data_directories = disk_dirs

    def teardown(self):
        shutil.rmtree(self.basic_config.GlobalConfiguration.log_dir)
        for disk_dir in self.basic_config.GlobalConfiguration.data_directories:
            shutil.rmtree(disk_dir)
