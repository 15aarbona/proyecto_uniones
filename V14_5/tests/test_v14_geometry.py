import sys
import unittest
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.config import MASKED_COLUMNS, N_ALMA_CLASSES, N_CANTONERA_CLASSES, N_Y, REGRESSION_ALWAYS  # noqa: E402
from core.losses import ConnectionDesignLossV14  # noqa: E402
from core.model import ConnectionDesignNetV14  # noqa: E402
from core.postprocess import geometry_counts  # noqa: E402


class V14GeometryTests(unittest.TestCase):
    def test_geometry_counts_from_distances(self):
        e = np.array([20.0])
        d = np.array([20.0])
        beam_d = np.array([100.0])
        beam_tf = np.array([10.0])
        p = np.array([[30.0, 60.0, 20.0, 60.0, 40.0] + [0.0] * (N_Y - 5)])

        n_alma, n_cantonera = geometry_counts(e, d, p, beam_d, beam_tf)

        self.assertEqual(n_alma.tolist(), [3])
        self.assertEqual(n_cantonera.tolist(), [1])

    def test_v14_forward_and_loss(self):
        torch.manual_seed(7)
        batch = 4
        model = ConnectionDesignNetV14(
            cat_cardinalities=[],
            num_continuous=10,
            n_standard_classes=3,
            p_mean_mm=[100.0] * N_Y,
            p_std_mm=[50.0] * N_Y,
            hidden_dim=32,
            num_blocks=1,
            dropout=0.1,
            gru_hidden_dim=16,
            n_p_bins=65,
            p_bin_step_mm=5.0,
        )
        criterion = ConnectionDesignLossV14(
            n_alma_weights=torch.ones(N_ALMA_CLASSES),
            n_cantonera_weights=torch.ones(N_CANTONERA_CLASSES),
            presence_pos_weight=torch.ones(len(MASKED_COLUMNS)),
            p_mean_mm=[100.0] * N_Y,
            p_std_mm=[50.0] * N_Y,
            n_p_bins=65,
            p_bin_step_mm=5.0,
            reg_mean_mm=torch.zeros(len(REGRESSION_ALWAYS)),
            reg_std_mm=torch.ones(len(REGRESSION_ALWAYS)),
        )

        x_cat = torch.zeros(batch, 0, dtype=torch.long)
        x_num = torch.randn(batch, 10)
        targets = {
            "standard_idx": torch.randint(0, 3, (batch,)),
            "bolt_idx": torch.randint(0, 7, (batch,)),
            "slip_critical": torch.randint(0, 2, (batch,)).float(),
            "n_alma_idx": torch.tensor([2, 3, 1, 2]),
            "n_cantonera_idx": torch.tensor([0, 2, 1, 0]),
            "n_rows_idx": torch.tensor([4, 7, 4, 4]),
            "reg_always": torch.randn(batch, len(REGRESSION_ALWAYS)),
            "masked_value": torch.zeros(batch, len(MASKED_COLUMNS)),
            "masked_mask": torch.zeros(batch, len(MASKED_COLUMNS)),
            "p_transition_idx": torch.zeros(batch, N_Y, dtype=torch.long),
            "beam_d_mm": torch.tensor([300.0, 400.0, 250.0, 350.0]),
            "beam_tf_mm": torch.tensor([10.0, 12.0, 8.0, 9.0]),
        }
        for i, (na, nc) in enumerate([(2, 0), (3, 2), (1, 1), (2, 0)]):
            k = na + nc + 1
            targets["masked_mask"][i, :k] = 1.0
            targets["masked_value"][i, :k] = torch.randn(k)

        outputs = model(x_cat, x_num, active_count=targets["n_rows_idx"] - 1)
        loss, parts = criterion(outputs, targets)

        self.assertEqual(tuple(outputs["n_rows_logits"].shape), (batch, N_Y + 2))
        self.assertNotIn("n_alma_logits", outputs)
        self.assertNotIn("n_cantonera_logits", outputs)
        self.assertTrue(torch.isfinite(loss))
        for key in ("geom_alma", "geom_cantonera", "geom_top", "geom_bottom"):
            self.assertIn(key, parts)


if __name__ == "__main__":
    unittest.main()
