from skywinder.ground.ground_configuration import GroundConfiguration
from skywinder.utils.log import setup_stream_handler, setup_file_handler
from skywinder.camera.pipeline.indexer import MergedIndex
from skywinder.communication.packet_classes import load_gse_packet_from_file
from skywinder.communication.file_format_classes import load_and_decode_file
import logging
import socket
import time

logger = logging.getLogger('skywinder.ground')


class LidarFileRelay(GroundConfiguration):
    def __init__(self, **kwargs):
        super(LidarFileRelay, self).__init__(**kwargs)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setblocking(True)
        self.socket.bind(self.lidar_downlink_forwarding_listen_address)
        self.socket.listen(1)
        self.lowrate_index = MergedIndex("*/*/*", data_dirs=['/data/gse_data'], index_filename='lowrate_index.csv',
                                         sort_on='epoch')
        self.file_index = MergedIndex("*/*", data_dirs=['/data/gse_data'], index_filename='file_index.csv',
                                      sort_on='first_timestamp')

    def run(self):
        while True:
            logger.info("Waiting for a connection")
            connection, client_address = self.socket.accept()
            last_lowrate_timestamp = time.time()
            last_highrate_timestamp = time.time()
            try:
                logger.info("Connection from %s" % str(client_address))
                done = False
                while not done:
                    self.lowrate_index.update()
                    df = self.lowrate_index.df
                    if df is None:
                        logger.info('Lowrate indices are empty.')
                    else:
                        # LIDAR Lowrate messages have message_id = 69 because the first character of the message is 'E'
                        selection = df[(df.message_id == 69) & (df.epoch > last_lowrate_timestamp)]
                        logger.debug('Found %d new lowrate files since %s' % (
                        len(selection), time.ctime(last_lowrate_timestamp)))
                        for k, row in selection.iterrows():
                            try:
                                lowrate_packet = load_gse_packet_from_file(row.filename)
                            except Exception:
                                logger.exception("Failure loading lowrate packet %s" % row.filename)
                                continue
                            try:
                                connection.sendall(lowrate_packet.payload)
                                logger.info(
                                    "Sent %d bytes from lowrate file %s" % (len(lowrate_packet.payload), row.filename))
                            except socket.error as e:
                                logger.warn("Encountered socket error %s, ending connection" % str(e))
                                raise e

                        if len(selection):
                            last_lowrate_timestamp = selection.epoch.max()
                            if last_lowrate_timestamp > time.time():
                                logger.critical("Invalid lowrate epoch detected %f > current time %f" % (
                                last_lowrate_timestamp, time.time()))

                    self.file_index.update()
                    df = self.file_index.df
                    if df is None:
                        logger.info('File indices are empty.')
                    else:
                        # LIDAR highrate files have camera_id 69 for short status messages or camera_id 252 for highrate telemetry files
                        selection = df[((df.camera_id == 69) | (df.camera_id == 252)) & (
                        df.first_timestamp > last_highrate_timestamp)]
                        logger.debug('Found %d new highrate files since %s' % (
                        len(selection), time.ctime(last_highrate_timestamp)))
                        for k, row in selection.iterrows():
                            try:
                                lidar_file = load_and_decode_file(row.filename)
                            except Exception:
                                logger.exception("Failure loading highrate file %s" % row.filename)
                                continue
                            try:
                                connection.sendall(lidar_file.payload)
                                logger.info("Sent %d bytes from file %s" % (len(lidar_file.payload), row.filename))
                            except socket.error as e:
                                logger.warn("Encountered socket error %s, ending connection" % str(e))
                                raise e

                        if len(selection):
                            last_highrate_timestamp = selection.first_timestamp.max()
                            if last_highrate_timestamp > time.time():
                                logger.critical("Invalid highrate epoch detected %f > current time %f" % (
                                last_highrate_timestamp, time.time()))

                    time.sleep(0.5)
            except Exception:
                logger.exception("resetting connection")
            try:
                connection.close()
            except Exception:
                logger.exception("Failure while closing connection")


if __name__ == "__main__":
    setup_stream_handler(level=logging.INFO)
    lfr = LidarFileRelay()
    lfr.run()
