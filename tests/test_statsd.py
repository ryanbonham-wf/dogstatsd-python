"""
Tests for dogstatsd.py
"""

from collections import deque
import time

from nose import tools as t

from statsd import statsd


class FakeSocket(object):
    """ A fake socket for testing. """

    def __init__(self):
        self.payloads = deque()

    def sendto(self, payload, address):
        self.payloads.append(payload)

    def recv(self):
        try:
            return self.payloads.popleft()
        except IndexError:
            return None

    def __repr__(self):
        return str(self.payloads)

class BrokenSocket(FakeSocket):

    def sendto(self, payload, address):
        raise Exception("Socket error")

class TestDogStatsd(object):

    def setUp(self):
        self.statsd = statsd
        self.statsd.socket = FakeSocket()

    def recv(self):
        return self.statsd.socket.recv()

    def test_set(self):
        self.statsd.set('set', 123)
        assert self.recv() == 'set:123|s'

    def test_gauge(self):
        self.statsd.gauge('gauge', 123.4)
        assert self.recv() == 'gauge:123.4|g'

    def test_counter(self):
        self.statsd.increment('page.views')
        t.assert_equal('page.views:1|c', self.recv())

        self.statsd.increment('page.views', 11)
        t.assert_equal('page.views:11|c', self.recv())

        self.statsd.decrement('page.views')
        t.assert_equal('page.views:-1|c', self.recv())

        self.statsd.decrement('page.views', 12)
        t.assert_equal('page.views:-12|c', self.recv())

    def test_histogram(self):
        self.statsd.histogram('histo', 123.4)
        t.assert_equal('histo:123.4|h', self.recv())

    def test_tagged_gauge(self):
        self.statsd.gauge('gt', 123.4, tags=['country:china', 'age:45', 'blue'])
        t.assert_equal('gt:123.4|g|#country:china,age:45,blue', self.recv())

    def test_tagged_counter(self):
        self.statsd.increment('ct', tags=['country:canada', 'red'])
        t.assert_equal('ct:1|c|#country:canada,red', self.recv())

    def test_tagged_histogram(self):
        self.statsd.histogram('h', 1, tags=['red'])
        t.assert_equal('h:1|h|#red', self.recv())

    def test_sample_rate(self):
        self.statsd.increment('c', sample_rate=0)
        assert not self.recv()
        for i in range(10000):
            self.statsd.increment('sampled_counter', sample_rate=0.3)
        self.assert_almost_equal(3000, len(self.statsd.socket.payloads), 150)
        t.assert_equal('sampled_counter:1|c|@0.3', self.recv())

    def test_tags_and_samples(self):
        for i in range(100):
            self.statsd.gauge('gst', 23, tags=["sampled"], sample_rate=0.9)

        def test_tags_and_samples(self):
            for i in range(100):
                self.statsd.gauge('gst', 23, tags=["sampled"], sample_rate=0.9)
            t.assert_equal('gst:23|g|@0.9|#sampled')

    def test_timing(self):
        self.statsd.timing('t', 123)
        t.assert_equal('t:123|ms', self.recv())

    @staticmethod
    def assert_almost_equal(a, b, delta):
        assert 0 <= abs(a - b) <= delta, "%s - %s not within %s" % (a, b, delta)

    def test_socket_error(self):
        self.statsd.socket = BrokenSocket()
        self.statsd.gauge('no error', 1)
        assert True, 'success'

    def test_timed(self):

        @self.statsd.timed('timed.test')
        def func(a, b, c=1, d=1):
            """docstring"""
            time.sleep(0.5)
            return (a, b, c, d)

        t.assert_equal('func', func.__name__)
        t.assert_equal('docstring', func.__doc__)

        result = func(1, 2, d=3)
        # Assert it handles args and kwargs correctly.
        t.assert_equal(result, (1, 2, 1, 3))

        packet = self.recv()
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        t.assert_equal('ms', type_)
        t.assert_equal('timed.test', name)
        self.assert_almost_equal(0.5, float(value), 0.1)

