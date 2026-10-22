import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import escenarios  # noqa: E402


def _fake_predict(filas):
    out = []
    for fila in filas:
        ratio = float(fila.get("ratio_moment", 0.0))
        con_cantonera = ratio >= 0.3
        out.append({
            "row": {
                "Unicode": fila.get("UNICODE"),
                "BEAM": "IPE300",
                "COLUMN": "HEB300",
                "Lh": 100.0 if con_cantonera else 0.0,
                "n_cantonera": 1 if con_cantonera else 0,
            },
            "check": {
                "cumple": ratio <= 0.6,
                "ratio_pesimo": ratio,
                "descripcion_ratio_pesimo": "test",
            },
            "n_cantonera": 1 if con_cantonera else 0,
            "raw": {},
        })
    return out


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "UNICODE": "U1",
            "BEAM": "IPE300",
            "COLUMN": "HEB300",
            "ratio_moment": 0.2,
            "ratio_shear": 0.1,
            "ratio_axial": 0.0,
        }

    def test_selects_three_scenarios(self):
        result = escenarios.generar_escenarios(
            self.row, _fake_predict, incremento=0.05, max_pasos=20, lote=4
        )
        found = {e["id"]: e for e in result["escenarios"] if e["encontrado"]}
        self.assertEqual(set(found), {"E1", "E2", "E3"})
        self.assertFalse(result["parcial"])
        self.assertIn("parada", result)
        self.assertIn("tiempo_s", result)
        self.assertEqual(result["parametros"]["timeout_s"], None)

    def test_timeout_returns_partial_results(self):
        def slow(filas):
            time.sleep(0.02)
            return _fake_predict(filas)

        result = escenarios.generar_escenarios(
            self.row, slow, incremento=0.05, max_pasos=20, lote=4, timeout_s=0.01
        )
        self.assertTrue(result["parcial"])
        self.assertEqual(result["parada"], "tiempo maximo alcanzado")
        self.assertTrue(result["avisos"])
        self.assertLessEqual(len(result["historial"]), 4)

    def test_refine_timeout_returns_partial_results(self):
        def raises(filas):
            raise TimeoutError("lote de refinado agotado")

        result = escenarios.generar_escenarios(
            self.row, raises, incremento=0.05, max_pasos=20, lote=4, timeout_s=60
        )
        self.assertTrue(result["parcial"])
        self.assertIn("timeout", result["parada"].lower())
        self.assertEqual(result["historial"], [])

    def test_caps_loads_and_stops_at_100_percent(self):
        row = dict(self.row, ratio_moment=0.95)
        result = escenarios.generar_escenarios(
            row, _fake_predict, incremento=0.05, max_pasos=20, lote=4
        )
        for paso in result["historial"]:
            self.assertLessEqual(paso["ratio_moment"], 1.0)


if __name__ == "__main__":
    unittest.main()
