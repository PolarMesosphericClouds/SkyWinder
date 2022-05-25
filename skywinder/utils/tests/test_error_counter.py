import os
import shutil
import tempfile

import nose.tools

from skywinder.utils import error_counter


class TestErrorCounter(object):
    def setup(self):
        self.logging_dir = tempfile.mkdtemp('counter_test')

    def teardown(self):
        shutil.rmtree(self.logging_dir, ignore_errors=True)

    def test_counter_with_default_names(self):
        ec = error_counter.CounterCollection('a_collection', self.logging_dir, 'events')
        repr(ec)
        ec.c1.reset()
        ec.events.increment()
        ec.c1.increment()

    def test_auto_make_dir(self):
        ec = error_counter.CounterCollection('a_collection', logging_dir=os.path.join(self.logging_dir, 'some_new_dir'))

    def test_auto_make_dirs(self):
        ec = error_counter.CounterCollection('a_collection', logging_dir=os.path.join(self.logging_dir, 'some_new_dir/some_other_dir'))

    def test_counter(self):
        ec = error_counter.CounterCollection('a_collection', logging_dir=self.logging_dir)
        repr(ec)
        ec.c1.reset()
        repr(ec)
        assert 'c1' in ec.counters
        ec.c2.reset()
        assert 'c2' in ec.counters
        ec.c3.reset()
        assert ec.filename is None
        with nose.tools.assert_raises(AttributeError):
            ec._invalid.reset()
        ec.c1.increment()
        assert ec.filename is not None
        with nose.tools.assert_raises(RuntimeError):
            ec.bad_counter.reset()
        ec.c1.increment()
        ec.c2.increment()
        ec.c3.increment()
        repr(ec)
        with open(ec.filename) as fh:
            lines = fh.readlines()
        assert len(lines) == 5
        header = lines[0].strip().split(',')
        assert header[0] == 'epoch'
        assert header[-1] == 'c3'
        data = lines[-1].strip().split(',')
        assert data[1] == '2'
        assert data[2] == '1'
        assert data[3] == '1'
