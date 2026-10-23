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

import checker  # noqa: E402
import model_registry  # noqa: E402
import predictor  # noqa: E402
import refinar  # noqa: E402
from calculador import CalculadorAISC36010  # noqa: E402


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

    def test_fastpaths_match_scalar_calculator(self):
        with open(CASO, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))[:3]
        predictions, _ = predictor.predict_and_check("V11", rows)
        for row in predictions:
            fast = CalculadorAISC36010(
                inp=checker.row_to_conexion_input(row)
            ).calcular_geometria()
            full = CalculadorAISC36010(
                inp=checker.row_to_conexion_input(row)
            ).calcular_conexion()
            expected = {
                c.descripcion: str(c.resultado)
                for c in full.complementarios[:18]
                if str(c.resultado).upper().startswith("REVISAR")
            }
            self.assertEqual(set(fast), set(expected))

            result = checker.check_single_row(row)
            self.assertEqual(result["cumple"], full.cumple)
            self.assertEqual(result["ratio_pesimo"], round(full.ratio_pesimo, 4))
            self.assertEqual(
                result["descripcion_ratio_pesimo"], full.descripcion_ratio_pesimo
            )
            self.assertEqual(
                result["ratios"], [f.model_dump() for f in full.ratios]
            )
            self.assertEqual(
                result["complementarios"],
                [c.model_dump() for c in full.complementarios],
            )


if __name__ == "__main__":
    unittest.main()
