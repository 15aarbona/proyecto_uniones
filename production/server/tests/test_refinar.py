import logging
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import refinar  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
