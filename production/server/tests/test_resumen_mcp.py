import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import checker  # noqa: E402
import main  # noqa: E402
from codame_schema import CODAME_COLUMNS  # noqa: E402


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
        "complementarios": [
            {"indice": 0, "descripcion": "G1", "resultado": "OK"},
            {"indice": 6, "descripcion": "SPACING_MIN", "resultado": "REVISAR: separacion minima 40 < 50"},
            {"indice": 29, "descripcion": "Numero de filas", "resultado": "2"},
        ],
    }
    base.update(kwargs)
    return base


def _codame(escenario):
    row = {c: 0 for c in CODAME_COLUMNS}
    row.update({"Unicode": "U1", "BEAM": "IPE300", "COLUMN": "HEB300",
                "Escenario": escenario})
    return row


class ResumenMCPTests(unittest.TestCase):
    def test_resumen_detecta_maximo_global_y_geometria(self):
        resumen = checker.resumen_comprobacion(_check())

        self.assertEqual(resumen["estado"], "NO_CUMPLE_AMBOS")
        self.assertEqual(resumen["ratio_max_todos"], 1.12)
        self.assertEqual(resumen["descripcion_ratio_max_todos"], "Slip Resistance")
        self.assertEqual(resumen["n_ratios_superan_1"], 1)
        self.assertEqual(resumen["n_fallos_geometricos"], 1)

    def test_detalle_incluye_todos_los_ratios_y_complementarios(self):
        detalle = checker.detalle_comprobacion(_check())

        self.assertEqual(len(detalle["ratios"]), 2)
        self.assertEqual(detalle["ratios"][0]["estado"], "OK")
        self.assertEqual(detalle["ratios"][1]["estado"], "EXCEDE")
        self.assertEqual(detalle["ratios"][1]["limite"], 1.0)
        self.assertEqual(len(detalle["complementarios"]), 3)
        self.assertEqual(detalle["complementarios"][0]["estado"], "OK")
        self.assertEqual(detalle["complementarios"][1]["estado"], "REVISAR")
        self.assertEqual(detalle["complementarios"][2]["estado"], "INFO")

    def _result(self):
        return {
            "rows": [_codame("E1 - Entrada"), _codame("E2 - Max")],
            "checks": [
                _check(Escenario="E1 - Entrada", cumple=True, ratio_pesimo=0.5,
                       descripcion_ratio_pesimo="Bolts in Tension",
                       ratios=[{"indice": 0, "descripcion": "Bolts in Tension", "ratio": 0.5}],
                       complementarios=[]),
                _check(Escenario="E2 - Max"),
            ],
            "escenarios": [
                {"id": "E1", "escenario": "Diseño de entrada", "encontrado": True,
                 "paso": 0, "factor_carga": 1.0, "ratio_moment": 0.5,
                 "ratio_shear": 0.1, "ratio_axial": 0.0, "cumple": True,
                 "Lh": 0.0, "n_cantonera": 0, "fuera_rango_entrenamiento": []},
                {"id": "E2", "escenario": "Máximo sin cantonera", "encontrado": True,
                 "paso": 5, "factor_carga": 0.6, "ratio_moment": 0.4,
                 "ratio_shear": 0.5, "ratio_axial": 0.05, "cumple": False,
                 "Lh": 0.0, "n_cantonera": 0, "fuera_rango_entrenamiento": []},
                {"id": "E3", "escenario": "Máximo con cantonera", "encontrado": False,
                 "codigo_motivo": "E3_SIN_CANTONERA", "motivo": "sin opcion"},
            ],
            "avisos": ["E1 no cumple"],
            "avisos_estructurados": [{"codigo": "E1_NO_CUMPLE", "mensaje": "E1 no cumple"}],
            "parada": "fin",
            "tiempo_s": 1.2,
        }

    def test_compact_result_estructura_nueva_sin_duplicados(self):
        compacto = main._compact_result("V12", self._result())

        self.assertNotIn("rows", compacto)
        self.assertNotIn("checks", compacto)
        self.assertNotIn("tabla_markdown", compacto)
        self.assertEqual(compacto["avisos"][0]["codigo"], "E1_NO_CUMPLE")
        self.assertEqual([e["escenario_id"] for e in compacto["escenarios"]],
                         ["E1", "E2", "E3"])

        e1 = compacto["escenarios"][0]
        self.assertEqual(len(e1["codame"]), len(CODAME_COLUMNS))
        self.assertEqual(e1["comprobacion"]["estado"], "CUMPLE")
        self.assertEqual(e1["cargas"]["ratio_moment"], 0.5)

        e2 = compacto["escenarios"][1]
        self.assertEqual(e2["comprobacion"]["estado"], "NO_CUMPLE_AMBOS")
        self.assertTrue(any(r["estado"] == "EXCEDE"
                            for r in e2["comprobacion"]["ratios"]))

        e3 = compacto["escenarios"][2]
        self.assertEqual(e3["motivo"]["codigo"], "E3_SIN_CANTONERA")

    def test_batch_counts_y_texto(self):
        compacto = main._compact_result("V12", self._result())
        resultados = [
            {"unicode": "U1", "status": "OK", "resultado": compacto},
            {"unicode": "U2", "status": "PERFIL_SIN_GEOMETRIA",
             "http_status": 422, "mensaje": "sin geometria"},
        ]
        resumen, errores = main._batch_counts(resultados)

        self.assertEqual(resumen["por_escenario"]["E1"]["cumple"], 1)
        self.assertEqual(resumen["por_escenario"]["E2"]["no_cumple"], 1)
        self.assertEqual(resumen["por_escenario"]["E3"]["no_encontrado"], 1)
        self.assertEqual(resumen["por_estado_conexion"]["PERFIL_SIN_GEOMETRIA"], 1)
        self.assertEqual(resumen["por_estado_escenario"]["CUMPLE"], 1)
        self.assertEqual(resumen["por_estado_escenario"]["NO_CUMPLE_AMBOS"], 1)
        self.assertEqual(len(errores), 1)

        conexiones = [
            {"unicode": "U1", "status": "OK", **compacto},
            {"unicode": "U2", "status": "PERFIL_SIN_GEOMETRIA", "escenarios": []},
        ]
        texto = main._resumen_texto(resumen, conexiones)
        self.assertIn("U1", texto)
        self.assertIn("PERFIL_SIN_GEOMETRIA", texto)

        respuesta = main._mcp_result({"status": "OK"}, texto)
        self.assertEqual(respuesta.structuredContent["status"], "OK")
        self.assertEqual(respuesta.content[0].text, texto)

    def test_validar_perfiles(self):
        self.assertIsNone(main._validar_perfiles({"BEAM": "IPE300", "COLUMN": "HEB300"}))
        problema = main._validar_perfiles({"BEAM": "UB406*152*60", "COLUMN": "HEB300"})
        self.assertIsNotNone(problema)
        self.assertIn("UB406*152*60", problema)


if __name__ == "__main__":
    unittest.main()
