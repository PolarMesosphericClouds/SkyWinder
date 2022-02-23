import numpy as np
from traitlets.config import Configurable
from traitlets import Int, Float
from pmc_turbo.camera.pipeline.write_images import percentiles_to_compute, percentile_keys
import logging
logger = logging.getLogger(__name__)

def get_percentiles_as_fractions(row,maximum_value=2**14-1):
    percentiles = [row[key]/float(maximum_value) for key in percentile_keys]
    return percentiles

class ExposureManager(Configurable):
    max_percentile_threshold_fraction = Float(default_value=0.9,min=0,max=1).tag(config=True)
    min_peak_threshold_fraction = Float(default_value=0.7, min =0,max=1).tag(config=True)
    min_percentile_threshold_fraction = Float(default_value=0.1,min=0,max=1).tag(config=True)
    adjustment_step_size_fraction = Float(default_value=0.05,min=0,max=1).tag(config=True)
    maximum_pixel_value = Int(default_value=2**14,min=0).tag(config=True)
    min_exposure = Int(default_value=35, min=0).tag(config=True)
    max_exposure = Int(default_value=700000,min=0).tag(config=True)
    close_exposure_time_threshold = Float(default_value=1e-4).tag(config=True)

    def __init__(self, **kwargs):
        super(ExposureManager,self).__init__(**kwargs)
        self.last_file_analyzed = None
        self.columns = ['epoch', 'max_percentile_threshold_fraction', 'min_peak_threshold_fraction',
                        'min_percentile_threshold_fraction', 'adjustment_step_size_fraction',
                        'min_exposure', 'max_exposure']

    def check_if_exposures_are_close(self,exposure_1, exposure_2):
        return (abs(exposure_1-exposure_2)/float(exposure_1) < self.close_exposure_time_threshold)

    def check_exposure(self, pipeline_status, file_statistics):
        if file_statistics.filename == self.last_file_analyzed:
            logger.info("Already attempted to update exposure from file %s, skipping update" % file_statistics.filename)
            return
        self.last_file_analyzed = file_statistics.filename
        current_exposure = int(float(pipeline_status['all_camera_parameters']['ExposureTimeAbs']))
        file_exposure = file_statistics.exposure_us
        if not self.check_if_exposures_are_close(current_exposure,file_exposure):
            logger.info("Current exposure reported by pipeline is %d, but latest file %s shows %d, "
                        "so skipping exposure update"
                        % (current_exposure, file_statistics.filename, file_exposure))
            return
        percentiles = get_percentiles_as_fractions(file_statistics,maximum_value=self.maximum_pixel_value)
        logger.debug("current exposure %d, percentiles: %s" %
                     (current_exposure, ','.join([('%.3f' % pct) for pct in percentiles])))
        factor = 1
        number_too_high = 0
        for pct in percentiles:
            if pct > self.max_percentile_threshold_fraction:
                number_too_high += 1
        number_too_low = 0
        if number_too_high == 0:
            if percentiles[-1] < self.min_peak_threshold_fraction:
                factor = self.min_peak_threshold_fraction/percentiles[-1]
                logger.debug("maximum is less than min_peak_threshold by factor of %f" % factor)
                if factor < (1+self.adjustment_step_size_fraction):
                    factor = 1+self.adjustment_step_size_fraction
                    logger.debug("factor is too insignificant, so bumping up to %f" % factor)
            else:
                for pct in percentiles:
                    if pct < self.min_percentile_threshold_fraction:
                        number_too_low += 1
                if number_too_low > 2:
                    factor = (1 + self.adjustment_step_size_fraction)**(number_too_low-2)
                    logger.debug("image is underexposed in %d bins, adjusting by %f" % (number_too_low, factor))
                else:
                    logger.debug("image is slightly underexposed in %d bins, not adjusting" % number_too_low)
        else:
            if number_too_high > 1:
                factor = (1-self.adjustment_step_size_fraction)**number_too_high
                logger.debug("image is overexposed in %d bins, adjusting by %f" % (number_too_high, factor))
            else:
                factor = 1
                logger.debug("image is less than 1 percent over exposed, not adjusting")

        new_exposure = int(factor*current_exposure)
        logger.debug("desired exposure %f" % (new_exposure))

        if new_exposure < self.min_exposure:
            logger.debug("desired exposure less than minimum")
            new_exposure = self.min_exposure
        if new_exposure > self.max_exposure:
            new_exposure = self.max_exposure
            logger.debug("desired exposure is more than maximum")

        if new_exposure == current_exposure:
            logger.debug("desired exposure is unchanged from current exposure")
            return
        logger.info("current exposure %d, new exposure %d" % (current_exposure,new_exposure))
        return new_exposure
