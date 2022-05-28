from nose.tools import assert_raises
import pytest

from skywinder.utils import log, configuration


def test_git_functions():
    log.git_hash()
    log.git_hash(short=False)
    log.git_status()
    log.git_log()

def test_log_functions():
    LOG_DIR = '/tmp'
    num_handlers = len(log.skywinder_logger.handlers)
    log.setup_stream_handler()
    log.setup_file_handler('pipeline',log_dir=LOG_DIR)
    log.setup_file_handler('controller',log_dir=LOG_DIR)
    log.setup_file_handler('communicator',log_dir=LOG_DIR)
    log.setup_file_handler('gse_receiver',log_dir=LOG_DIR)
    with assert_raises(ValueError):
        log.setup_file_handler('unknown')
    log.skywinder_logger.handlers = log.skywinder_logger.handlers[:num_handlers]

@pytest.mark.skip(reason="Directory dependent and non-essential. Works on computers with appropriate directories, but not CI yet. Set up with CI is low priority.")
def test_log_functions_with_custom_file_handler():
    LOG_DIR = '/tmp'
    num_handlers = len(log.skywinder_logger.handlers)
    log.setup_stream_handler()
    log.setup_file_handler('pipeline',log_dir=LOG_DIR)
    log.setup_file_handler('controller',log_dir=LOG_DIR)
    log.setup_file_handler('communicator',log_dir=LOG_DIR)
    log.setup_file_handler('gse_receiver',log_dir=LOG_DIR)
    with assert_raises(ValueError):
        log.setup_file_handler('unknown')
    log.setup_file_handler('known_unknown', logger=log.skywinder_logger)
    log.skywinder_logger.handlers = log.skywinder_logger.handlers[:num_handlers]
