import glob
import os
import logging

import pandas as pd

from skywinder.communication.command_table import command_manager
from skywinder.communication.packet_classes import get_command_packet_from_buffer
from skywinder.ground.ground_configuration import GroundConfiguration
from skywinder.utils.index_watcher import IndexWatcher

logger=logging.getLogger(__name__)


class CommandHistory(GroundConfiguration):
    def __init__(self, directory_to_watch=None, **kwargs):
        super(CommandHistory,self).__init__(**kwargs)
        self.set_directory(directory_to_watch)
        self.watcher = None
        self.history = None

    def set_directory(self,directory_to_watch=None):
        if directory_to_watch:
            self.directory_to_watch = directory_to_watch
        else:
            dirs = glob.glob(os.path.join(self.root_data_path,self.command_history_subdir,'2*'))
            dirs.sort()
            logger.debug("Found command history dir %s" % dirs[-1])
            self.directory_to_watch = dirs[-1]
        self.index_filename = os.path.join(self.directory_to_watch,self.command_index_filename)
        self.watcher = IndexWatcher(self.index_filename)

    def update(self):
        fragment = self.watcher.get_fragment()
        if fragment is None:
            return
        rows_to_add = []
        for k,row in fragment.iterrows():
            try:
                with open(row.command_blob_file,'r') as fh:
                    command_packet = get_command_packet_from_buffer(fh.read())
                    commands = command_manager.decode_commands(command_packet.payload)
            except Exception:
                logger.exception("Failed to parse commands for file %s" % row.command_blob_file)
                continue
            for (name,kwargs) in commands:
                result = row.copy()
                result['command_name'] = name
                result['arguments'] = kwargs
                rows_to_add.append(result)
        if self.history is None:
            self.history = pd.DataFrame(rows_to_add)
        else:
            self.history = pd.concat([self.history,pd.DataFrame(rows_to_add)],ignore_index=True)
        self.watcher.add_fragment(fragment)
        return len(rows_to_add)
