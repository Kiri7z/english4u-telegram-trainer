import unittest
from concurrent.futures import ThreadPoolExecutor
from security_controls.rate_limit import SlidingWindowLimiter


class RateLimitTests(unittest.TestCase):
    def test_window_expires_without_locking_other_users(self):
        now = [1.0]
        limiter = SlidingWindowLimiter(2, 300, clock=lambda: now[0])
        self.assertEqual(limiter.consume('a'), 0)
        self.assertEqual(limiter.consume('a'), 0)
        self.assertEqual(limiter.consume('a'), 300)
        self.assertEqual(limiter.consume('b'), 0)
        now[0] += 300
        self.assertEqual(limiter.consume('a'), 0)

    def test_concurrent_attempts_do_not_exceed_limit(self):
        limiter = SlidingWindowLimiter(5, 300)
        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(limiter.consume, ['user'] * 50))
        self.assertEqual(results.count(0), 5)

    def test_full_storage_does_not_evict_an_active_limit(self):
        now = [1.0]
        limiter = SlidingWindowLimiter(1, 300, max_keys=2, clock=lambda: now[0])
        self.assertEqual(limiter.consume('a'), 0)
        self.assertEqual(limiter.consume('b'), 0)
        self.assertEqual(limiter.consume('c'), 300)
        self.assertEqual(limiter.consume('a'), 300)
        now[0] += 300
        self.assertEqual(limiter.consume('c'), 0)


if __name__ == '__main__':
    unittest.main()
