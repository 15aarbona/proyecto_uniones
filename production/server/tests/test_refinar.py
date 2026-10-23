import logging
import sys
import threading
import time
import unittest
from concurrent.futures import Future
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import refinar  # noqa: E402


class _FakeExecutor:
    def __init__(self):
        self.futures = []

    def submit(self, fn, *args, **kwargs):
        fut = Future()
        self.futures.append(fut)
        return fut

    def shutdown(self, wait=True, cancel_futures=False):
        pass


def _rows(n=8):
    base = {
        "Unicode": "T",
        "UNICODE": "T",
        "BEAM": "IPE300",
        "COLUMN": "HEB300",
        "ratio_moment": 0.5,
        "ratio_shear": 0.2,
        "ratio_axial": 0.0,
    }
    return [dict(base, Unicode=f"T{i}", UNICODE=f"T{i}") for i in range(n)]


class RefineBackendTests(unittest.TestCase):
    def setUp(self):
        refinar.log.setLevel(logging.CRITICAL)

    def tearDown(self):
        backend = refinar.get_backend()
        backend.reset()

    def test_backends_accept_maximize_load(self):
        rows = _rows(4)
        serial = refinar.SerialBackend().map_refine(rows, True, False)
        self.assertEqual(len(serial), 4)

        process = refinar.ProcessPoolBackend()
        process.start()
        try:
            parallel = process.map_refine(rows, True, False)
        finally:
            process.close()
        self.assertEqual(len(parallel), 4)

    def test_refine_many_uses_three_argument_backend(self):
        # 4+ filas es el minimo para entrar por el backend en paralelo.
        rows = _rows(8)
        result = refinar.refine_many(rows, with_check=False, maximize_load=False)
        self.assertEqual(len(result), 8)

    def test_refine_timeout_is_timeout_error(self):
        self.assertTrue(issubclass(refinar.RefineTimeout, TimeoutError))

    def test_map_refine_releases_lock_while_waiting(self):
        backend = refinar.ProcessPoolBackend()
        fake = _FakeExecutor()
        backend._executor = fake
        result = []

        thread = threading.Thread(
            target=lambda: result.append(backend.map_refine([{}, {}], True, False))
        )
        thread.start()
        deadline = time.monotonic() + 2.0
        while len(fake.futures) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(len(fake.futures), 2)

        acquired = backend._lock.acquire(timeout=0.2)
        if acquired:
            backend._lock.release()
        for fut in fake.futures:
            fut.set_result(({}, None))
        thread.join(timeout=2.0)
        backend._executor = None

        self.assertTrue(acquired, "map_refine retiene el lock mientras espera")
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(result[0]), 2)


if __name__ == "__main__":
    unittest.main()
