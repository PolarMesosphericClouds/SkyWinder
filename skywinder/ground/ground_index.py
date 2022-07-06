import glob
from skywinder.camera.pipeline.indexer import MergedIndex

def get_file_index(data_dir_glob='/data/gse_data/2*',sort_on='last_timestamp'):
    data_dirs = glob.glob(data_dir_glob)
    data_dirs.sort()
    return MergedIndex('*', data_dirs=data_dirs, index_filename='file_index.csv', sort_on=sort_on)
