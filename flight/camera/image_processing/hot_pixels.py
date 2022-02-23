import numpy as np

class HotPixelMasker(object):
    def __init__(self, hot_pixels,image_shape,min_radius=1,max_range=2):
        self.min_radius = min_radius
        self.max_range=max_range
        self.image_shape = image_shape
        self.hot_pixels = hot_pixels
        if len(hot_pixels):
            self.xindexes,self.yindexes = compute_surrounding_indexes(self.hot_pixels,self.image_shape,
                                                                  min_radius=min_radius, max_range=max_range)
        else:
            self.xindexes = []
            self.yindexes = []

    def process(self,image):
        if len(self.hot_pixels):
            return mask_hot_pixels(image,self.hot_pixels,xindexes=self.xindexes, yindexes=self.yindexes)
        else:
            return image

def compute_surrounding_indexes(hot_pixels,image_shape,min_radius=1,max_range=2):
    """
    make a list of indexes of the pixels surrounding the given list of pixels

    the regions wrap around the image edges

    Parameters
    ----------
    hot_pixels : shape = (num_pixels,2)
    image_shape : 2-tuple,
     matching the last dimensio of hot_pixels, used to wrap the indicies
    min_radius
     minimum manhattan distance from pixel to include
    max_range
     maximum range to icnldue from pixel
    Returns
    -------

    """
    offsets = np.array([(x,y) for x in range(-max_range,max_range+1)
                        for y in range(-max_range,max_range+1)
                        if (abs(x)+abs(y))>min_radius])
    # the followign arrays will have shape (num_pixels,num_offsets)
    xindexes = np.mod(offsets[None,:,0] + hot_pixels[:,0,None], image_shape[0])
    yindexes = np.mod(offsets[None,:,1] + hot_pixels[:,1,None], image_shape[1])
    return xindexes,yindexes

def mask_hot_pixels(image,hot_pixels,xindexes,yindexes,reduction_function=np.median):
    out = image.copy()
    regions = image[xindexes,yindexes]
    out[hot_pixels[:,0],hot_pixels[:,1]] = reduction_function(regions,axis=1)
    return out