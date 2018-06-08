"""
This module contains Classes for measuring and collecting metrics, such as time elapsed,
number of times some code has been executed, etc.
"""
import statistics
import time


class Timer:
    """
    Tracks how long an operation took.

    You can use it as a context manager::

        with Timer() as timer:
            something()
        how_long = timer.elapsed
        print(timer)  # Prints "Timer took X.XXXs."

    or as an object::

        timer = Timer()
        timer.start()
        some_long_operation()
        another()
        timer.stop()

    You can also pause the timer for more complex measurements::

        timer = Timer()
        timer.start()
        some_long_operation()
        timer.pause()
        dont_count_this()
        timer.start()
        another()
        timer.stop()

    """

    def __init__(self, name=None):
        self.name = name
        self.state = 'new'
        self.elapsed = 0.0

    def __enter__(self, name=None):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    def __str__(self):
        return "{} took {:.3f}s".format(
            self.get_name(), self.elapsed,
        )

    def get_name(self):
        return "Timer `{}`".format(self.name) if self.name else 'Timer'

    def start(self):
        if self.state == 'stopped':
            raise RuntimeWarning("{} was already stopped.".format(self.get_name()))
        self.state = 'running'
        self.start_time = time.time()

    def pause(self):
        if self.state != 'running':
            raise RuntimeWarning("{} is not running.".format(self.get_name()))
        self.state = 'paused'
        self.elapsed += (time.time() - self.start_time)

    def stop(self):
        self.state = 'stopped'
        self.elapsed += (time.time() - self.start_time)

    @property
    def __value__(self):
        return self.elapsed


class Counter:
    """
    Counts how many times a block of code is executed in the given amount of
    time::

        counter = Counter(duration=5)  # run for 5 seconds
        while counter.on:
            await some_async()
        how_long = counter.elapsed  # hopefully `5`
        how_many = counter.clicks
        print(counter)  # Prints "Counter called X times in 5.000s. (Z.ZZZc/s)"

        counter = Counter(count=15)  # run 15 times
        while counter.on:
            await some_async()
        how_long = counter.elapsed
        how_many = counter.clicks  # hopefully `15`
        print(counter)  # Prints "Counter called 15 times in Y.YYYs. (Z.ZZZc/s)"

    """

    def __init__(self, duration=None, count=None, name=None, verbosity=0):
        if duration is None and count is None:
            raise ValueError(
                "Invalid arguments for this counter. You must specify either "
                "`duration` or `count`."
            )
        self.duration = duration
        self._duration = duration
        self.count = count
        self.name = name
        self.verbosity = verbosity
        self.clicks = 0
        self.start_time = None
        self.end_time = None

    def start(self):
        self.start_time = time.time()
        if self.duration is not None:
            self.end_time = self.start_time + self.duration
        return self

    @property
    def __value__(self):
        if self._duration is not None:
            return self.clicks
        elif self.count is not None:
            return self.elapsed

    @property
    def elapsed(self):
        now = time.time()
        if now <= self.end_time:
            return time.time() - self.start_time
        else:
            return self.duration

    @property
    def on(self):
        if self.start_time is None:
            self.start()
        if self.duration is not None:
            now = time.time()
            on = now <= self.end_time
        elif self.count is not None:
            on = self.clicks < self.count

        if on:
            self.clicks += 1
            if self.verbosity > 0:
                print(self)
        else:
            if self.end_time is None:
                self.end_time = time.time()
                self.duration = self.end_time - self.start_time
        return on

    @property
    def rate(self):
        return self.clicks / float(self.duration)

    def __str__(self):
        if self.name is not None:
            name = "`{}` ".format(self.name)
        else:
            name = ''
        return "Counter {}called {} times in {:.3f}s. ({:.3f}c/s)".format(
            name, self.clicks, self.elapsed, self.rate,
        )


class StatAggregator:

    """
    A ``StatAggregator`` aggregates values across 'stats' instances.

    A 'stats' instance is any instance that has a numerical attribute you want
    to aggregate over (default: ``__value__``).

    Stats are added with the `.push(stat)` method.

    The aggregation values mirror the :mod:`~statistics` module
    of the stdlib, with
    the addition of ``total``, ``min``, ``max`` and ``count``.

    """
    def __init__(self, fmt=None, attribute=None):
        self.fmt = fmt
        if attribute is None:
            attribute = '__value__'
        self.attribute = attribute
        self.stats = []

    def __str__(self):
        if self.fmt is not None:
            return self.fmt.format(stats=self)

        return "StatAggregator with {} values.".format(
            self.count,
        )

    def push(self, value):
        self.stats.append(value)

    @property
    def values(self):
        return [getattr(stat, self.attribute, stat) for stat in self.stats]

    @property
    def min(self):
        return min(self.values)

    @property
    def max(self):
        return max(self.values)

    @property
    def total(self):
        return sum(self.values)

    @property
    def count(self):
        return len(self.values)

    @property
    def mean(self):
        return statistics.mean(self.values)

    @property
    def harmonic_mean(self):
        return statistics.harmonic_mean(self.values)

    @property
    def median(self):
        return statistics.median(self.values)

    @property
    def median_low(self):
        return statistics.median_low(self.values)

    @property
    def median_high(self):
        return statistics.median_high(self.values)

    @property
    def mode(self):
        return statistics.mode(self.values)

    @property
    def pstdev(self):
        return statistics.pstdev(self.values)

    @property
    def pvariance(self):
        return statistics.pvariance(self.values)

    @property
    def stdev(self):
        return statistics.stdev(self.values)

    @property
    def variance(self):
        return statistics.variance(self.values)
