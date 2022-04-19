import numpy as np


def equal_or_close(value1,value2):
    if type(value1) is float:
        return np.allclose(value1,value2)
#    if type(value1) is str:
#        return value1 == value2[:value2.find('\x00')]
    else:
        return value1 == value2