import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.config import P_COLUMNS  # noqa: E402
from core.dataset import zone_targets  # noqa: E402


class ZoneTargetTests(unittest.TestCase):
    def test_split_viga_cantonera_and_bottom_margin(self):
        row = {c: 0.0 for c in P_COLUMNS}
        row.update({"p1": 20.0, "p2": 30.0, "p3": 40.0, "p4": 110.0})
        row.update(
            {
                "e": 0.0,
                "d": 10.0,
                "BEAM_d_mm": 100.0,
                "n_alma": 2,
                "n_cantonera": 1,
            }
        )
        z = zone_targets(pd.DataFrame([row]))
        np.testing.assert_allclose(z["p_viga"][0, :2], [20.0, 30.0])
        np.testing.assert_allclose(z["p_cantonera"][0, :1], [40.0])
        self.assertGreater(z["bottom_margin"][0], 0.0)


if __name__ == "__main__":
    unittest.main()
