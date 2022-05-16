import warnings as _warnings
import os as _os
try:
    import Pyro4
    Pyro4.config.SERVERTYPE = 'multiplex'
    Pyro4.config.SERIALIZERS_ACCEPTED = {'pickle','json'}
    Pyro4.config.SERIALIZER = 'pickle'
except ImportError as e:
    _warnings.warn("Could not import Pyro4: many things will not work properly! Error was %r" % e)

root_dir = _os.path.abspath(_os.path.split(__file__)[0])