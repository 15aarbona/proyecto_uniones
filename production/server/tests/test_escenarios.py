import asyncio
import json
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
import escenarios  # noqa: E402
import main  # noqa: E402


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
        self.assertNotIn("parcial", result)
        self.assertIn("parada", result)
        self.assertIn("tiempo_s", result)
        self.assertEqual(result["parametros"]["timeout_s"], None)

    def test_timeout_raises_instead_of_returning_partial(self):
        def slow(filas):
            time.sleep(0.02)
            return _fake_predict(filas)

        with self.assertRaises(TimeoutError):
            escenarios.generar_escenarios(
                self.row, slow, incremento=0.05, max_pasos=20, lote=4, timeout_s=0.01
            )

    def test_refine_timeout_propagates(self):
        def raises(filas):
            raise TimeoutError("lote de refinado agotado")

        with self.assertRaises(TimeoutError):
            escenarios.generar_escenarios(
                self.row, raises, incremento=0.05, max_pasos=20, lote=4, timeout_s=60
            )

    def test_caps_loads_and_stops_at_100_percent(self):
        row = dict(self.row, ratio_moment=0.95)
        result = escenarios.generar_escenarios(
            row, _fake_predict, incremento=0.05, max_pasos=20, lote=4
        )
        for paso in result["historial"]:
            self.assertLessEqual(paso["ratio_moment"], 1.0)

    def test_scenario_gate_rejects_when_queue_full_or_timed_out(self):
        async def run():
            gate = main._ScenarioGate(max_workers=2, max_queue=1, queue_timeout=0.05)
            await gate.acquire()
            await gate.acquire()

            # El 3o entra en la unica plaza de cola; el 4o recibe ocupado al instante.
            waiter = asyncio.create_task(gate.acquire())
            await asyncio.sleep(0.01)
            with self.assertRaises(main.ServerBusyError):
                await gate.acquire()

            # Si no se libera ningun worker a tiempo, el 3o tambien recibe ocupado.
            with self.assertRaises(main.ServerBusyError):
                await waiter
            # El timeout de cola no debe liberar por error una plaza de worker.
            self.assertEqual(gate.status()["active"], 2)

            gate.release()
            gate.release()
            self.assertEqual(gate.status()["active"], 0)
            self.assertEqual(gate.status()["waiting"], 0)

        asyncio.run(run())

    def test_client_timeout_budget_covers_queue_plus_execution(self):
        self.assertLess(
            config.SCENARIO_QUEUE_TIMEOUT_S + config.SCENARIO_TIMEOUT_S,
            config.CLIENT_TIMEOUT_S,
        )
        self.assertTrue(main.mcp.settings.json_response)
        self.assertGreaterEqual(config.SCENARIO_BATCH_ROWS, 1)

    def test_parse_mcp_rows_accepts_list_object_and_json(self):
        rows = [dict(self.row, UNICODE="A"), dict(self.row, UNICODE="B")]
        self.assertEqual([r["UNICODE"] for r in main._parse_mcp_rows(rows)], ["A", "B"])
        self.assertEqual([r["UNICODE"] for r in main._parse_mcp_rows(self.row)], ["U1"])
        self.assertEqual(
            [r["UNICODE"] for r in main._parse_mcp_rows(json.dumps(rows))], ["A", "B"]
        )

    def test_batch_runs_sequentially_and_continues_after_timeout(self):
        rows = [dict(self.row, UNICODE=u) for u in ("A", "B", "C")]
        calls = []
        original = main.escenarios.run

        def fake_run(name, row, timeout_s=None, **kwargs):
            calls.append(row["UNICODE"])
            if row["UNICODE"] == "B":
                raise TimeoutError("agotado")
            return {
                "tabla_markdown": row["UNICODE"], "checks": [], "rows": [],
                "rows_raw": [], "escenarios": [], "historial": [], "parada": "ok",
                "tiempo_s": 0.1, "avisos": [], "parametros": {},
            }

        main.escenarios.run = fake_run
        try:
            out = main._run_batch_sync("V11", rows, {}, timeout_s=10)
        finally:
            main.escenarios.run = original

        self.assertEqual(calls, ["A", "B", "C"])
        self.assertEqual([r["status"] for r in out], ["OK", "TIMEOUT_SERVIDOR", "OK"])

    def test_batch_rejects_profile_without_geometry_before_predicting(self):
        rows = [dict(self.row, UNICODE="BAD", BEAM="UB406*152*60")]
        called = []
        original = main.escenarios.run

        def fake_run(*args, **kwargs):
            called.append(args)
            return {}

        main.escenarios.run = fake_run
        try:
            out = main._run_batch_sync("V11", rows, {}, timeout_s=10)
        finally:
            main.escenarios.run = original

        self.assertEqual(called, [])
        self.assertEqual(out[0]["status"], "PERFIL_SIN_GEOMETRIA")
        self.assertEqual(out[0]["http_status"], 422)
        self.assertIn("UB406*152*60", out[0]["mensaje"])


if __name__ == "__main__":
    unittest.main()
