import sys
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from batcher import InferenceBatcher  # noqa: E402


class _FakeAdapter:
    def __init__(self, fail_values=()):
        self.calls = []
        self.fail_values = set(fail_values)
        self.lock = threading.Lock()

    def predict(self, features, bundle):
        with self.lock:
            self.calls.append(len(features))
        if features["value"].isin(self.fail_values).any():
            raise ValueError("valor no admitido")
        return pd.DataFrame({"out": features["value"].to_numpy()})


class BatcherTests(unittest.TestCase):
    def setUp(self):
        self.batcher = None

    def tearDown(self):
        if self.batcher is not None:
            self.batcher.close()

    def _start(self, max_rows=64, max_wait_ms=20):
        self.batcher = InferenceBatcher(max_rows=max_rows, max_wait_ms=max_wait_ms)
        self.batcher.start()
        return self.batcher

    def test_concurrent_requests_share_one_forward(self):
        adapter = _FakeAdapter()
        batcher = self._start(max_rows=64, max_wait_ms=30)
        bundle = {"adapter": adapter}

        def submit(tag):
            features = pd.DataFrame({"value": [tag] * 8})
            return batcher.submit(bundle, features).result(timeout=5)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, [1, 2]))

        self.assertEqual([len(r) for r in results], [8, 8])
        self.assertEqual(adapter.calls, [16])

    def test_large_request_is_split(self):
        adapter = _FakeAdapter()
        batcher = self._start(max_rows=10)
        features = pd.DataFrame({"value": list(range(25))})
        result = batcher.submit({"adapter": adapter}, features).result(timeout=5)
        self.assertEqual(len(result), 25)
        self.assertEqual(adapter.calls, [10, 10, 5])

    def test_one_bad_request_does_not_break_the_others(self):
        adapter = _FakeAdapter(fail_values={-1})
        batcher = self._start(max_rows=64, max_wait_ms=30)
        bundle = {"adapter": adapter}
        bad = batcher.submit(bundle, pd.DataFrame({"value": [-1] * 2}))
        good = batcher.submit(bundle, pd.DataFrame({"value": [7] * 2}))
        # La peticion mala se aisla y solo su future falla.
        with self.assertRaises(ValueError):
            bad.result(timeout=5)
        self.assertEqual(len(good.result(timeout=5)), 2)

    def test_wait_window_does_not_block_without_traffic(self):
        adapter = _FakeAdapter()
        batcher = self._start(max_rows=64, max_wait_ms=0)
        start = time.monotonic()
        result = batcher.submit({"adapter": adapter}, pd.DataFrame({"value": [1]})).result(timeout=5)
        self.assertEqual(len(result), 1)
        self.assertLess(time.monotonic() - start, 1.0)


if __name__ == "__main__":
    unittest.main()
