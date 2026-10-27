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
                    "V12", {"UNICODE": "R1", "__web_id": 4}, {}, 5.0
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


if __name__ == "__main__":
    unittest.main()
