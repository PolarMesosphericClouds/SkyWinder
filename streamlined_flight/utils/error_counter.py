import collections
import time
import os
import csv


class CounterCollection(object):
    def __init__(self, name, logging_dir, *args):
        """
        A collection of counters for logging exceptional events

        This class is a container for holding event counters that automatically log their values to disk when a value changes.
        The counters can be accessed as attributes of the instance of the class

        Example usage
        -------------
        cc = CounterCollection('unlikely_events','/tmp/logs')
        cc.earthquakes.reset() # reset is a dummy method that can be used to set up the counter, it does not trigger a write to the log file
        cc.tsunamis.reset()
        cc.volcanos.reset()

        cc.earthquakes.increment()  #this will trigger a write to the log file
        cc.tsunamis.increment()
        cc.tsunamis.increment()     # after this, the last line of the log will have values 1,2,0 for earthquakes, tsunamis, and volcanos

        cc.cyclones.reset() # this will raise a RuntimeError because you can't add a counter once the log file has been written to

        Parameters
        ----------
        name : str
            The name of this collection of counters
        logging_dir : str
            The directory in which the log of counter values will be written
        args : additional str arguments
            An initial set of Counter objects can be set up during instantiation if desired by passing strings
            representing the counter names

        Raises
        ------
        RuntimeError if an attempt to access a new counter is made after the log file has already been written

        """
        self.counters = collections.OrderedDict()
        self.logging_dir = logging_dir
        if not os.path.exists(self.logging_dir):
            os.makedirs(self.logging_dir)
        self.name = name
        self.filename = None
        for counter_name in args:
            self.counters[counter_name] = Counter(counter_name, parent=self)

    def __getattr__(self, item):
        if item in self.__dict__:
            return self.__dict__[item]
        counter = self.counters.get(item, None)
        if counter is None:
            if self.filename is None:
                if item.startswith('_'):
                    raise AttributeError("Adding counters with name having leading underscore is not supported")
                counter = Counter(item, parent=self)
                self.counters[item] = counter
                self.__dict__[item] = counter  # add to __dict__ to enable tab completion
            else:
                raise RuntimeError("Cannot create a new counter '%s' for collection '%s' because the counter log file "
                                   "is already open\nThe existing counters are: %r"
                                   % (item, self.name, list(self.counters.keys())))
        return counter

    def _write(self):
        epoch = time.time()
        if not self.filename:
            self.filename = os.path.join(self.logging_dir, self.name + time.strftime('_%Y-%m-%d_%H%M%S.csv'))
            with open(self.filename, 'a') as fh:
                csv.writer(fh, quoting=csv.QUOTE_NONE).writerow(['epoch'] + list(self.counters.keys()))
        with open(self.filename, 'a') as fh:
            csv.writer(fh, quoting=csv.QUOTE_NONE).writerow(['%f' % epoch] + [str(x) for x in list(self.counters.values())])

    def __repr__(self):
        items = [repr(value) for (key, value) in list(self.counters.items())]
        if not items:
            items = ['<empty>']
        return self.name + ' counters:\n\t' + '\n\t'.join(items)


class Counter(object):
    def __init__(self, name, parent=None):
        """
        A class to keep track of a number of events that have occured.

        This class is not intended to be used by itself, it is automatically invoked by the CounterCollection class

        By default the counters cause the parent CounterCollection to write all values to disk any time they update.
        This can be disabled by setting the "lazy" attribute to True

        Parameters
        ----------
        name : str
            The name of the event to keep track of
        parent : CounterCollection
            The CounterCollection instance that logs changes to this counter
        """
        self.name = name
        self.value = 0
        self.parent = parent
        self.lazy = False

    def __repr__(self):
        return '%s : %s' % (self.name, str(self.value))

    def __str__(self):
        return str(self.value)

    def reset(self):
        self.value = 0

    def increment(self):
        self.value += 1
        if self.parent and not self.lazy:
            self.parent._write()
