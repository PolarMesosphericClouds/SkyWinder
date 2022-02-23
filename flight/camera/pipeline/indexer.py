import glob
import logging
import os
import gc

import pandas as pd

from pmc_turbo.utils.index_watcher import IndexWatcher

logger = logging.getLogger(__name__)

DEFAULT_DATA_DIRS = ['/data1', '/data2', '/data3', '/data4']
INDEX_FILENAME = 'index.csv'


class MergedIndex(object):
    def __init__(self, subdirectory_name, data_dirs=DEFAULT_DATA_DIRS, index_filename=INDEX_FILENAME,
                 sort_on='frame_timestamp_ns'):
        self.data_dirs = data_dirs
        self.subdirectory_name = subdirectory_name
        self.index_filename = index_filename
        self.index_filenames = []
        self.watchers = []
        self.df = None
        self.sort_on = sort_on
        self.update()

    def get_index_filenames(self):
        index_filenames = []
        for data_dir in self.data_dirs:
            index_filenames.extend(glob.glob(os.path.join(data_dir, self.subdirectory_name, self.index_filename)))
        return index_filenames

    def update_watchers(self):
        index_filenames = self.get_index_filenames()
        new_index_files = list(set(index_filenames).difference(set(self.index_filenames)))
        if new_index_files:
            logger.info("found new index files: %r" % new_index_files)
        new_watchers = [IndexWatcher(fn) for fn in new_index_files]
        self.watchers = self.watchers + new_watchers
        self.index_filenames = index_filenames

    def update(self):
        self.update_watchers()
        new_rows = False
        segment = None

        for watcher in self.watchers:
            fragment = watcher.get_fragment()
            if fragment is not None and fragment.shape[0] > 0:
                logger.debug("Found %d new rows in %s" % (fragment.shape[0], watcher.filename))
                new_rows = True
                if segment is None:
                    segment = fragment
                else:
                    segment = pd.concat((segment, fragment), ignore_index=True)
        if new_rows:
            if self.sort_on:
                segment.sort_values(self.sort_on, inplace=True)
            if self.df is None:
                self.df = segment
            else:
                self.df = pd.concat((self.df, segment), ignore_index=True)
            logger.debug("index updated with new rows, %d total rows" % self.df.shape[0])
        else:
            if self.df is None:
                msg = "index is empty"
            else:
                msg = "%d total rows" % self.df.shape[0]
            logger.debug("index updated, no new rows, " + msg)
        gc.collect()

    def get_latest(self, update=True):
        if update:
            self.update()
        if self.df is not None and self.df.shape[0]:
            return self.df.iloc[-1:].copy().iloc[0]
        else:
            return None

    def get_index_of_timestamp(self, timestamp, update=True):
        if update:
            self.update()
        if self.df is None:
            return None
        else:
            return self.df.frame_timestamp_ns.searchsorted(timestamp * 1e9, side='right')[0]
