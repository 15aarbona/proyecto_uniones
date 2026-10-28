import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402


def _fake_result(row):
    uid = row.get("UNICODE")
    return {
        "rows": [{"Unicode": uid, "Escenario": "E1 - Entrada"}],
        "checks": [{"Escenario": "E1 - Entrada", "cumple": True,
                    "ratios": [], "complementarios": []}],
        "rows_raw": [{"Unicode": uid, "raw": True}],
        "escenarios": [{"id": "E1", "escenario": "Entrada",
                        "encontrado": True, "cumple": True}],
        "historial": [{"paso": 0}],
        "tabla": [{"Escenario": "E1"}],
        "tabla_markdown": "| ... |",
        "parametros": {},
        "parada": "fin",
        "tiempo_s": 0.01,
        "avisos": [],
        "avisos_estructurados": [],
    }


class ScenarioBatchTests(unittest.TestCase):
    def test_compact_web_result_quita_bloques_pesados_y_conserva_raw(self):
        compacto = main._compact_web_result(_fake_result({"UNICODE": "U1"}))

        for clave in ("historial", "tabla", "tabla_markdown", "parametros"):
            self.assertNotIn(clave, compacto)
        for clave in ("rows", "checks", "rows_raw", "escenarios", "parada", "tiempo_s"):
            self.assertIn(clave, compacto)

    def test_run_one_scenario_incluye_prediccion_raw(self):
        original = main.escenarios.run
        main.escenarios.run = lambda name, row, **opts: _fake_result(row)
        try:
            out = asyncio.run(
                main._run_one_scenario(
                    "V12",
                    {"UNICODE": "R1", "__web_id": 4, "BEAM": "IPE300",
                     "COLUMN": "HEB300", "ratio_moment": 0.5,
                     "ratio_shear": 0.1, "ratio_axial": 0.0},
                    {}, 5.0,
                )
            )
        finally:
            main.escenarios.run = original

        self.assertEqual(out["status"], "OK")
        self.assertEqual(out["web_id"], 4)
        self.assertIn("rows_raw", out["resultado"])
        self.assertEqual(out["resultado"]["rows_raw"][0]["raw"], True)
        self.assertNotIn("historial", out["resultado"])

    def test_job_asincrono_avanza_por_polling(self):
        rows = [{"UNICODE": f"J{i}", "__web_id": i} for i in range(3)]
        llamadas = []
        original = main._run_one_scenario

        async def fake_one(name, row, options, timeout_s):
            llamadas.append(row["UNICODE"])
            await asyncio.sleep(0)
            return {
                "unicode": row["UNICODE"],
                "web_id": row["__web_id"],
                "status": "OK",
                "resultado": {"rows": [], "checks": [], "rows_raw": [],
                              "escenarios": []},
            }

        main._run_one_scenario = fake_one
        main._BATCH_JOBS.pop("job-test", None)
        try:
            async def scenario():
                creado = await main.create_scenarios_job(
                    main.ScenarioJobIn(client_id="job-test", rows=rows)
                )
                self.assertEqual(creado["job_id"], "job-test")
                for _ in range(100):
                    data = await main.get_scenarios_job("job-test", since=0, limit=1)
                    if data["estado"] == "hecho" and data["done"] >= 3:
                        return data
                    await asyncio.sleep(0.01)
                return data

            data = asyncio.run(scenario())
        finally:
            main._run_one_scenario = original
            main._BATCH_JOBS.pop("job-test", None)

        self.assertEqual(sorted(llamadas), ["J0", "J1", "J2"])
        self.assertEqual(data["total"], 3)
        self.assertEqual(data["done"], 3)
        self.assertEqual(data["estado"], "hecho")
        self.assertEqual(len(data["resultados"]), 1)


    def test_lanzar_parte_en_subjobs_y_descarga_paginada(self):
        rows = [
            {"UNICODE": f"L{i}", "BEAM": "IPE300", "COLUMN": "HEB300",
             "ratio_moment": 0.5, "ratio_shear": 0.1, "ratio_axial": 0.0}
            for i in range(60)
        ]

        async def fake_one(name, row, options, timeout_s):
            await asyncio.sleep(0)
            return {
                "unicode": row.get("UNICODE"),
                "web_id": row.get("__web_id"),
                "fila": row.get("__web_id"),
                "status": "OK",
                "resultado": _fake_result(row),
            }

        original = main._run_one_scenario
        main._run_one_scenario = fake_one
        main._BATCH_JOBS.clear()
        try:
            async def scenario():
                lanzado = await main.lanzar_escenarios(
                    rows=rows, model="V12", client_id="launch-test"
                )
                estado = "PROCESANDO"
                esperado = None
                for _ in range(200):
                    esperado = await main.esperar_trabajo("launch-test", timeout_s=5)
                    estado = esperado.structuredContent["estado"]
                    if estado in ("LISTO", "ERROR"):
                        break
                    await asyncio.sleep(0.01)
                pagina = await main.descargar_resultado(
                    "launch-test", pagina=1, por_pagina=10, detalle="completo"
                )
                resumen = await main.descargar_resultado(
                    "launch-test", pagina=1, por_pagina=1, detalle="resumen"
                )
                return lanzado, estado, pagina, resumen

            lanzado, estado, pagina, resumen = asyncio.run(scenario())
        finally:
            main._run_one_scenario = original
            main._BATCH_JOBS.clear()

        self.assertEqual(lanzado.structuredContent["n_subjobs"], 3)
        self.assertEqual(estado, "LISTO")
        pag = pagina.structuredContent
        self.assertEqual(pag["total"], 60)
        self.assertEqual(pag["n_paginas"], 6)
        self.assertEqual(len(pag["conexiones"]), 10)
        self.assertEqual(pag["conexiones"][0]["fila"], 0)
        self.assertIn("codame", pag["conexiones"][0]["escenarios"][0])
        comp = resumen.structuredContent["conexiones"][0]["escenarios"][0]["comprobacion"]
        self.assertNotIn("ratios", comp)
        self.assertNotIn("complementarios", comp)

    def test_lanzar_limita_filas(self):
        rows = [
            {"UNICODE": f"X{i}", "BEAM": "IPE300", "COLUMN": "HEB300"}
            for i in range(main.config.SCENARIO_JOB_MAX_ROWS + 1)
        ]

        async def scenario():
            return await main.lanzar_escenarios(rows=rows, client_id="limite-test")

        res = asyncio.run(scenario())
        self.assertEqual(res.structuredContent["status"], "ERROR_ENTRADA")
        self.assertEqual(res.structuredContent["http_status"], 413)

    def test_esperar_trabajo_no_encontrado(self):
        res = asyncio.run(main.esperar_trabajo("no-existe", timeout_s=0.5))
        self.assertEqual(res.structuredContent["estado"], "NO_ENCONTRADO")

    def test_esperar_trabajo_timeout(self):
        rows = [{"UNICODE": "S1", "BEAM": "IPE300", "COLUMN": "HEB300",
                 "ratio_moment": 0.5, "ratio_shear": 0.1, "ratio_axial": 0.0}]

        async def slow_one(name, row, options, timeout_s):
            await asyncio.sleep(0.6)
            return {
                "unicode": row.get("UNICODE"),
                "web_id": row.get("__web_id"),
                "fila": row.get("__web_id"),
                "status": "OK",
                "resultado": _fake_result(row),
            }

        original = main._run_one_scenario
        main._run_one_scenario = slow_one
        main._BATCH_JOBS.clear()
        try:
            async def scenario():
                await main.lanzar_escenarios(rows=rows, client_id="timeout-test")
                primero = await main.esperar_trabajo("timeout-test", timeout_s=0.5)
                await asyncio.sleep(0.3)
                segundo = await main.esperar_trabajo("timeout-test", timeout_s=5)
                return primero, segundo

            primero, segundo = asyncio.run(scenario())
        finally:
            main._run_one_scenario = original
            main._BATCH_JOBS.clear()

        self.assertTrue(primero.structuredContent.get("timeout"))
        self.assertEqual(segundo.structuredContent["estado"], "LISTO")


if __name__ == "__main__":
    unittest.main()
