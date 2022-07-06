import bisect
import os
import glob
from collections import OrderedDict
import logging

import sys
from traitlets.config import Application
from traitlets import Unicode,List,Enum

import skywinder.utils.configuration

logger = logging.getLogger(__name__)
import skywinder.communication.short_status
from skywinder.ground.ground_configuration import GroundConfiguration


class LowrateMonitor(GroundConfiguration):
    def __init__(self,max_initial_files=100,**kwargs):
        super(LowrateMonitor,self).__init__(**kwargs)
        self.gse_root_dir = self.find_latest_gse_dir()
        self.lowrate_data = OrderedDict()
        self.by_message_id = {}
        self.bad_files = set()
        self.update(max_initial_files)

    def find_latest_gse_dir(self):
        dirs = glob.glob(os.path.join(self.root_data_path,'2*'))
        dirs.sort()
        logger.debug("Found gse dir %s" % dirs[-1])
        return dirs[-1]

    @property
    def message_ids(self):
        return list(self.by_message_id.keys())

    def latest(self,message_id):
        latest_file = self.by_message_id[message_id][-1]
        latest =  self.lowrate_data[latest_file]
        logger.debug("latest file for message id %d is %s" % (message_id, latest_file))
        return latest, latest_file

    def update(self, max_files=0,lowrate_file_suffix=''):
        filenames = glob.glob(os.path.join(self.gse_root_dir,'*/lowrate/*'+lowrate_file_suffix))
        filenames += glob.glob(os.path.join(self.gse_root_dir,'*/payloads/*.short_status'))
        filenames.sort(key=lambda x: os.path.split(x)[1])
        if max_files:
            skipped_files = filenames[:-max_files]
            self.lowrate_data.update(list(zip(skipped_files,[{} for _ in range(len(skipped_files))])))
            filenames = filenames[-max_files:]
        logger.debug("Found %d total filenames" % len(filenames))
        added = 0
        for filename in filenames[::-1]:
            filename_index = os.path.split(filename)[1]
            if filename_index in self.lowrate_data:
                if added:
                    logger.info("added %d files" % added)
                return
            if filename in self.bad_files:
                continue
            try:
                if filename.endswith('.short_status'):
                    with open(filename,'r') as fh:
                        payload = fh.read()
                    values = skywinder.communication.short_status.load_short_status_from_payload(payload).values
                else:
                    values = skywinder.communication.short_status.load_short_status_from_file(filename).values
            except Exception:
                logger.exception("Failed to open %s" % filename)
                self.bad_files.add(filename)
                continue
            message_id = values['message_id']
            current_list = self.by_message_id.get(message_id,[])
            bisect.insort(current_list,filename_index)
            self.by_message_id[message_id] = current_list
            self.lowrate_data[filename_index] = values
            added += 1
        if added:
            logger.info("added %d files" % added)

class LowrateMonitorApp(Application):
    config_file = Unicode('', help="Load this config file").tag(config=True)
    config_dir = Unicode(skywinder.utils.configuration.default_ground_config_dir, help="Config file directory").tag(config=True)
    write_default_config = Unicode('', help="Write template config file to this location").tag(config=True)
    classes = List([LowrateMonitor])
    mode = Enum(['full', 'piggyback'],default_value='full', help="configuration shortcut to setup for piggyback or full system").tag(config=True)
    aliases = dict(generate_config='LowrateMonitorApp.write_default_config',
                   config_file='LowrateMonitorApp.config_file',
                   mode='LowrateMonitorApp.mode')

    def initialize(self, argv=None):
        actual_argv = argv
        if argv is None:
            actual_argv = sys.argv
        print("initializing LowrateMonitor with arguments:",actual_argv)
        self.parse_command_line(argv)
        if self.write_default_config:
            with open(self.write_default_config, 'w') as fh:
                fh.write(self.generate_config_file())
                self.exit()
        if self.config_file:
            print("**** Ignoring any --mode option ****")
        else:
            if self.mode == 'full':
                print("Using full configuration mode")
                self.config_file = 'default_ground_config.py'
            elif self.mode == 'piggyback':
                print("Using piggyback configuration mode")
                self.config_file = 'piggyback_ground_config.py'
            else:
                raise RuntimeError("Unexpected usage: either specify --config_file or use a valid --mode option")
        print('loading config: ', self.config_dir, self.config_file)
        self.load_config_file(self.config_file, path=self.config_dir)

        print(self.config)
        self.lowrate_monitor = LowrateMonitor(config=self.config)
