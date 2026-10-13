"""Bounded, process-local sliding windows for a single-instance deployment."""

import math
import time
from collections import OrderedDict, deque
from threading import Lock


class SlidingWindowLimiter:
    def __init__(self, limit, window_seconds, max_keys=4096, clock=time.monotonic):
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self.clock = clock
        self._buckets = OrderedDict()
        self._lock = Lock()

    def consume(self, key):
        """Return zero if allowed, otherwise the seconds until an attempt is allowed."""
        with self._lock:
            now = self.clock()
            cutoff = now - self.window_seconds
            # Buckets are ordered by their last accepted attempt.
            while self._buckets:
                oldest_key, oldest = next(iter(self._buckets.items()))
                if oldest[-1] > cutoff:
                    break
                del self._buckets[oldest_key]

            attempts = self._buckets.get(key)
            if attempts is None:
                if len(self._buckets) >= self.max_keys:
                    oldest = next(iter(self._buckets.values()))
                    return max(1, math.ceil(oldest[-1] + self.window_seconds - now))
                attempts = deque()
                self._buckets[key] = attempts

            while attempts and attempts[0] <= cutoff:
                attempts.popleft()
            if len(attempts) >= self.limit:
                return max(1, math.ceil(attempts[0] + self.window_seconds - now))

            attempts.append(now)
            self._buckets.move_to_end(key)
            return 0

    def reset(self, key):
        with self._lock:
            self._buckets.pop(key, None)
