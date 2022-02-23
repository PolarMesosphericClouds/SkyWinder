import numpy as np
from matplotlib import pyplot as plt
import cv2
from collections import namedtuple
import scipy.optimize
import logging

logger = logging.getLogger(__name__)

class Blob(object):
    def __init__(self,x=None,y=None,peak=None,sigma=None):
        self.x = x
        self.y = y
        self.peak = peak
        self.sigma = sigma
    def __repr__(self):
        return 'Blob(x=%r,y=%r,peak=%r,sigma=%r)' % (self.x, self.y, self.peak, self.sigma)

def find_blobs(image,threshold=1000,cell_size=32,max_blobs_per_cell=1):
    dilated_image = cv2.dilate(image,cv2.getStructuringElement(cv2.MORPH_DILATE,(3,3)))
    #dilated_cells = dilated_image.reshape((image.shape[0]//cell_size,cell_size,image.shape[1]//cell_size,cell_size))
    cells = image.reshape((image.shape[0]//cell_size,cell_size,image.shape[1]//cell_size,cell_size))
    blobs = []
    for cellx in range(cells.shape[0]):
        for celly in range(cells.shape[2]):
            cell = cells[cellx,:,celly,:]
            possible_peaks = np.flatnonzero(cell > threshold)
            peaks = []
            for peak in possible_peaks:
                x,y = np.unravel_index(peak,(cell_size,cell_size))
                imagex = x + cellx*cell_size
                imagey = y + celly*cell_size
                if dilated_image[imagex,imagey] == image[imagex,imagey]: # true if we are at a local maximum
                    peaks.append(peak)
            peak_values = cell.flatten()[peaks]
            ordering = peak_values.argsort()
            peaks = np.array(peaks)
            for peak in peaks[ordering[-max_blobs_per_cell:]]:
                x,y = np.unravel_index(peak,(cell_size,cell_size))
                imagex = x + cellx*cell_size
                imagey = y + celly*cell_size
                blobs.append(Blob(imagex,imagey,image[imagex,imagey],None))
    return blobs


def gauss2d(params,xgrid,ygrid):
    A,x0,y0,sigmasq,offset = params
    gaussian = A*np.exp(-(((xgrid-x0)**2 + (ygrid-y0)**2)/(2*sigmasq))) + offset
    return gaussian

def objective(params,xgrid,ygrid,zdata):
    gaussian = gauss2d(params,xgrid,ygrid)
    return np.sum(np.abs((zdata-gaussian))**2)

def fit_gauss_2d(data,A0 = None, x0 = None, y0 = None, sigma0 = 1, offset = None):
    if x0 is None:
        x0 = data.shape[0]/2.0
        y0 = data.shape[1]/2.0
    if offset is None:
        offset = data.min()
    if A0 is None:
        A0 = data.ptp()
    init_params = (A0,x0,y0,sigma0**2,offset)
    ygrid,xgrid = np.meshgrid(np.arange(data.shape[1]),np.arange(data.shape[0]))
    return xgrid,ygrid,scipy.optimize.minimize(objective,init_params,args=(xgrid,ygrid,data))

class BlobFinder(object):
    def __init__(self, im, blob_threshold=6, kernel_size=8, kernel_sigma=2, fitting_region_size=32, fit_blobs=True,
                 cell_size=128, max_blobs_per_cell=1, rmax=4):

        kernel = cv2.getGaussianKernel(kernel_size,sigma=kernel_sigma)
        kernel = np.outer(kernel,kernel)
        # zero out the pixels that will make the "trough" before normalizing so that the mean will end up being zero
        # after adding the trough
        kernel[0,:] = 0
        kernel[:,0] = 0
        kernel[-1,:] = 0
        kernel[:,-1] = 0
        kernel = kernel/kernel.sum()

        # npix is the total number of pixels in the trough
        npix = kernel.shape[0]*4-2
        kernel[0,:] = -1.0/npix
        kernel[:,0] = -1.0/npix
        kernel[-1,:] = -1.0/npix
        kernel[:,-1] = -1.0/npix
        self.kernel = kernel
        #convolve
        imlev =  cv2.filter2D(im.astype('float'),-1,kernel)

        # Make sure that the leveled image can be divided evenly by the cell_size
        nr = (imlev.shape[0]//cell_size)*cell_size
        nc = (imlev.shape[1]//cell_size)*cell_size
        # leveled is the filtered image that is an even multiple of the cell_size
        self.leveled = imlev[:nr,:nc]
        cells = self.leveled.reshape((imlev.shape[0]//cell_size,cell_size,
                                        imlev.shape[1]//cell_size,cell_size))
        #calculate noise
        noise = np.median(cells.std(axis=(1,3)))
        self.global_noise = noise
        self.cells = cells

        #find blobs, now using local MAD noise estimate. threshold is in units of MAD
        blobs = self.find_blobs(threshold=blob_threshold,cell_size=cell_size,
                                max_blobs_per_cell=max_blobs_per_cell, rmax=rmax)
        #fit blobs
        if fit_blobs:
            for blob in blobs:
                xmin = np.max((blob.x - fitting_region_size // 2, 0))
                xmax = np.min((blob.x + fitting_region_size // 2, im.shape[0] - 1))
                ymin = np.max((blob.y - fitting_region_size // 2, 0))
                ymax = np.min((blob.y + fitting_region_size // 2, im.shape[1] - 1))

                stamp = im[xmin:xmax,ymin:ymax]
                xgrid,ygrid,result = fit_gauss_2d(stamp)
                blob.sigma = result.x[3]
        self.blobs = blobs
    def find_blobs(self,threshold=6,cell_size=32,max_blobs_per_cell=1, rmax=4):
        """

        Parameters
        ----------
        threshold
        cell_size
        max_blobs_per_cell
        rmax : radius in pixels for two blobs to be considered the same object

        Returns
        -------

        """
        rsquared = rmax**2

        cells = self.leveled.reshape((self.leveled.shape[0]//cell_size,cell_size,self.leveled.shape[1]//cell_size,cell_size))
        blobs = []
        for cellx in range(cells.shape[0]):
            for celly in range(cells.shape[2]):
                cell = cells[cellx,:,celly,:]

                median = np.median(cell)
                deviations = cell-median
                cell_mad = np.median(np.abs(deviations))
                possible_peaks = np.flatnonzero(deviations > threshold*cell_mad)

                peakxy = []
                peak_values = cell.flatten()[possible_peaks]
                ordering = peak_values.argsort()[::-1]  #reverse the ordering because we want to order from largest
                # to smallest brightness
                possible_peaks = possible_peaks[ordering]
                # iterate through peaks in descending brightness order
                for peak in possible_peaks:
                    x,y = np.unravel_index(peak,(cell_size,cell_size))
                    if len(peakxy):
                        pxy = np.array(peakxy)
                        distances = (pxy[:,0]-x)**2 + (pxy[:,1]-y)**2
                        if np.any(distances<rsquared):
                            # this peak is close to an already found peak, so we skip it
                            continue
                    imagex = x + cellx*cell_size
                    imagey = y + celly*cell_size
                    blobs.append(Blob(imagex,imagey,self.leveled[imagex,imagey],None))
                    if len(blobs) >= max_blobs_per_cell:
                        break
        #unify blobs that were detected in more than one cell
        blobs.sort(key=lambda x:x.peak,reverse=True)
        bxy = []
        unique_blobs = []
        for blob in blobs:
            if len(bxy):
                pxy = np.array(bxy)
                distances = (pxy[:,0]-blob.x)**2 + (pxy[:,1]-blob.y)**2
                if np.any(distances<rsquared):
                    continue
            bxy.append((blob.x,blob.y))
            unique_blobs.append(blob)
        return unique_blobs
