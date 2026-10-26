import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import artifacts  # noqa: E402
import main  # noqa: E402


def _result(uid="U1"):
    return {
        "unicode": uid,
        "status": "OK",
        "resultado": {
            "parada": "ratio_moment al 100 %",
            "escenarios": [
                {"id": "E1", "escenario": "Entrada", "encontrado": True, "paso": 0,
                 "cumple": True, "ratio_pesimo": 0.8},
                {"id": "E2", "escenario": "Sin cantonera", "encontrado": False,
                 "motivo": "sin opcion"},
                {"id": "E3", "escenario": "Con cantonera", "encontrado": True, "paso": 2,
                 "cumple": True, "ratio_pesimo": 0.9, "Lh": 100.0, "n_cantonera": 1},
            ],
            "rows": [
                {"Escenario": "E1 - Entrada", "Unicode": f"{uid}_E00",
                 "BEAM": "HEB200", "COLUMN": "HEB200"},
                {"Escenario": "E3 - Con cantonera", "Unicode": f"{uid}_E02",
                 "BEAM": "HEB200", "COLUMN": "HEB200", "Lh": 100.0},
            ],
            "checks": [
                {"Escenario": "E1 - Entrada", "cumple": True, "ratio_pesimo": 0.8},
                {"Escenario": "E3 - Con cantonera", "cumple": True, "ratio_pesimo": 0.9},
            ],
        },
    }


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_parquet_has_three_design_rows_per_connection(self):
        meta = artifacts.save_scenarios([_result("U1"), _result("U2")], "V11", directory=self.tmp)
        self.assertEqual(meta["formato"], "parquet")
        self.assertEqual(meta["filas"], 6)
        path = artifacts.get_path(meta["id"], directory=self.tmp)
        self.assertIsNotNone(path)
        df = pd.read_parquet(path)
        self.assertEqual(len(df), 6)
        self.assertEqual(set(df["Escenario"]), {"E1", "E2", "E3"})
        self.assertTrue((df["UNICODE"] == "U1").sum() == 3)
        found = df[(df["UNICODE"] == "U1") & (df["Escenario"] == "E3")].iloc[0]
        self.assertTrue(bool(found["Encontrado"]))
        self.assertEqual(found["BEAM"], "HEB200")
        self.assertTrue(bool(found["check_cumple"]))

    def test_summary_is_small_and_complete(self):
        results = [_result(f"U{i}") for i in range(10)]
        resumen, errores = main._batch_summary(results)
        self.assertEqual(len(resumen), 10)
        self.assertEqual(errores, [])
        markdown = main._summary_markdown(resumen)
        self.assertLess(len(markdown), 3000)
        self.assertIn("UNICODE", markdown)
        self.assertIn("E1", markdown)

    def test_artifact_url_and_invalid_id(self):
        meta = artifacts.save_scenarios([_result()], "V11", directory=self.tmp)
        self.assertTrue(meta["url"].endswith(".parquet"))
        self.assertIsNone(artifacts.get_path("../../etc/passwd", directory=self.tmp))
        self.assertIsNone(artifacts.get_path("0" * 32, directory=self.tmp))

    def test_empty_artifact_is_valid_parquet(self):
        meta = artifacts.save_scenarios([], "V11", directory=self.tmp)
        path = artifacts.get_path(meta["id"], directory=self.tmp)
        df = pd.read_parquet(path)
        self.assertEqual(len(df), 0)


if __name__ == "__main__":
    unittest.main()
