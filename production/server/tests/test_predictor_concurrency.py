import csv
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
ROOT = SERVER_DIR.parents[1]
CASO = ROOT / "caso.csv"
WEIGHTS = SERVER_DIR / "models" / "V11" / "weights.pt"

sys.path.insert(0, str(SERVER_DIR))

import model_registry  # noqa: E402
import predictor  # noqa: E402
import refinar  # noqa: E402


@unittest.skipUnless(CASO.exists() and WEIGHTS.exists(), "requiere caso.csv y modelo V11")
class PredictorConcurrencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        model_registry.activate_configured()
        predictor.start_inference()

    @classmethod
    def tearDownClass(cls):
        predictor.shutdown_inference()
        refinar.shutdown_backend()

    def test_concurrent_predictions_are_consistent(self):
        with open(CASO, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))[:2]
        self.assertGreaterEqual(len(rows), 2)

        def call(_):
            return predictor.predict_and_check("V11", rows)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(call, range(2)))

        expected = [r.get("UNICODE") for r in rows]
        for predictions, checks in results:
            self.assertEqual(len(predictions), len(rows))
            self.assertEqual(len(checks), len(rows))
            self.assertEqual([p.get("Unicode") for p in predictions], expected)
        stats = predictor._get_batcher().stats()
        self.assertGreaterEqual(stats["batches"], 1)
        self.assertGreaterEqual(stats["rows"], len(rows))


if __name__ == "__main__":
    unittest.main()
