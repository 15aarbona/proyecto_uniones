import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import checker  # noqa: E402
import main  # noqa: E402


def _check(**kwargs):
    base = {
        "Unicode": "U1",
        "cumple": False,
        "ratio_pesimo": 0.87,
        "descripcion_ratio_pesimo": "Column flange thickness by yield line method",
        "ratios": [
            {"indice": 6, "descripcion": "Column flange thickness by yield line method", "ratio": 0.87},
            {"indice": 16, "descripcion": "Slip Resistance", "ratio": 1.12},
        ],
        "complementarios": [],
    }
    base.update(kwargs)
    return base


class ResumenMCPTests(unittest.TestCase):
    def test_resumen_detecta_maximo_global_y_geometria(self):
        check = _check(
            complementarios=[
                {
                    "indice": 6,
                    "descripcion": "SPACING_MIN",
                    "resultado": "REVISAR: separacion minima 40 < 50",
                }
            ]
        )

        resumen = checker.resumen_comprobacion(check)

        self.assertEqual(resumen["estado"], "NO_CUMPLE_AMBOS")
        self.assertEqual(resumen["ratio_max_todos"], 1.12)
        self.assertEqual(resumen["descripcion_ratio_max_todos"], "Slip Resistance")
        self.assertEqual(resumen["n_ratios_superan_1"], 1)
        self.assertEqual(resumen["n_fallos_geometricos"], 1)
        self.assertIn("Slip Resistance", resumen["dictamen"])
        self.assertIn("SPACING_MIN", resumen["dictamen"])

    def test_resumen_cumple(self):
        check = _check(
            cumple=True,
            ratios=[
                {"indice": 6, "descripcion": "Column flange thickness by yield line method", "ratio": 0.62},
            ],
            ratio_pesimo=0.62,
        )

        resumen = checker.resumen_comprobacion(check)

        self.assertEqual(resumen["estado"], "CUMPLE")
        self.assertIn("Cumple AISC 360-10", resumen["dictamen"])
        self.assertIn("0.62", resumen["dictamen"])

    def test_compact_result_anade_resumen_y_mantiene_tablas(self):
        result = {
            "checks": [
                _check(Escenario="E1 - Entrada"),
                _check(
                    Escenario="E2 - Maximo sin cantonera",
                    cumple=True,
                    ratio_pesimo=0.5,
                    descripcion_ratio_pesimo="Bolts in Tension",
                    ratios=[
                        {"indice": 0, "descripcion": "Bolts in Tension", "ratio": 0.5},
                    ],
                ),
            ],
            "escenarios": [
                {
                    "id": "E1", "encontrado": True, "cumple": False,
                    "ratio_pesimo": 0.87,
                    "descripcion_ratio_pesimo": "Column flange thickness by yield line method",
                },
                {
                    "id": "E2", "encontrado": True, "cumple": True,
                    "ratio_pesimo": 0.5,
                    "descripcion_ratio_pesimo": "Bolts in Tension",
                },
                {"id": "E3", "encontrado": False, "motivo": "sin opcion de cantonera"},
            ],
            "rows": [],
            "tabla": [{"Escenario": "E1"}],
            "tabla_markdown": "tabla completa",
            "parada": "fin",
            "avisos": [],
        }

        compacto = main._compact_result("V11", result)

        self.assertEqual(compacto["tabla_markdown"], "tabla completa")
        self.assertEqual(compacto["tabla"], [{"Escenario": "E1"}])
        self.assertIn("resumen_comprobacion", compacto["escenarios"][0])
        self.assertNotIn("ratios", compacto["escenarios"][0]["resumen_comprobacion"])
        self.assertNotIn("complementarios", compacto["escenarios"][0]["resumen_comprobacion"])
        self.assertNotIn("ratios", compacto["checks"][0])
        self.assertNotIn("complementarios", compacto["checks"][0])

        resumen, errores = main._batch_summary([
            {"unicode": "U1", "status": "OK", "resultado": compacto}
        ])

        self.assertEqual(errores, [])
        self.assertEqual(resumen[0]["ratio_max_todos"], 1.12)
        self.assertEqual(resumen[0]["escenario_ratio_max_todos"], "E1")
        self.assertEqual(resumen[0]["estado_comprobacion"], "NO_CUMPLE")
        self.assertIn("E3: no encontrado", resumen[0]["dictamen"])


if __name__ == "__main__":
    unittest.main()
