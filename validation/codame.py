"""
Modulo de validacion con CODAME.

API principal:
    from validation.codame import validate_csv
    df = validate_csv("resultado_v_pru.csv")   # -> DataFrame [Unicode, Estado, <18 ratios>, RatioPesimo, DescripRatioPesimo]

Que hace:
  1. Lee un CSV con los disenos (salida de V_pru o equivalente).
  2. Traduce cada fila a las columnas que espera CODAME (model_to_row).
  3. Las escribe en bloque en `Tabla_MOMENT_M1` de un libro de Excel YA ABIERTO
     (CalcCodame.exe se engancha a esa instancia por COM: GetActiveObject).
  4. Lanza `CalcCodame.exe` UNA vez por lote y lee `TResultadosRatios` /
     `TResultadosComplemen`.
  5. Restaura el contenido original de la tabla (no guarda el libro).

Requiere:
  - Windows con Excel de escritorio x64 y `pywin32`.
  - El libro CONNEXTOR abierto en Excel.
  - Lanzar bajo `runas /netonly` para que la autenticacion de red (SQL) use la
    cuenta de dominio. La contrasena nunca la maneja este modulo.

Columnas que necesita el CSV (se admiten alias):
  Input  : UNICODE, BEAM, COLUMN, Capacity_Moment/Shear/Axial (+ _Percentage),
           grado_acero (o AceroEstructural), clase_tornillo (o EstandarTornillos)
  Diseno : standard, Bolt, SlipCritical, g, e, d, Bp, tp, Lh, p1..p12,
           tws, ts, tbs, tst, n_alma, n_cantonera
  Feats  : BEAM_tf_mm, fy_acero_mpa, fu_acero_mpa  (si faltan, se rellenan del
           catalogo Tekla eu/cad y de la tabla de aceros)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import win32com.client as win32
except ImportError as e:  # pragma: no cover
    raise ImportError("Este modulo requiere pywin32 (pip install pywin32)") from e

from .model_to_row import model_to_row

# ---------------------------------------------------------------------------
# Configuracion del libro / exe
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parents[1]

SHEET_MOMENT = "IM_MOMENT"
TABLE_MOMENT = "Tabla_MOMENT_M1"
TABLE_RATIOS = "TResultadosRatios"
TABLE_COMPLEMEN = "TResultadosComplemen"
ACCION = "CALCULAR_CODAME"
OBJ_MAPEO = "CodigoMOMENTAgregadorCODAME0"
OBJ_CALC = "MOMENT_CODAMEaux"

DEFAULT_EXE = REPO / "CalcCodame" / "CalcCodame.exe"
DEFAULT_WORKBOOK_NAME = "CONNEXTOR"
# Libro que se abre automaticamente si no hay ninguno abierto en Excel
DEFAULT_WORKBOOK_CANDIDATES = [
    REPO / "CalcCodame" / "CONNEXTOR - CRIS.xlsm",
    REPO / "production" / "excel_client" / "CONNEXTOR - CRIS_final.xlsm",
]


def _default_workbook_path():
    for p in DEFAULT_WORKBOOK_CANDIDATES:
        if p.exists():
            return p
    return None

SENTINEL = -2146826252  # error/N-A devuelto por CODAME en algun check

# Tabla de aceros (si el CSV no trae fy/fu)
ACERO_TABLE = {"S275JR": (275.0, 430.0), "S355JR": (355.0, 490.0)}

UNICODE_ALIASES = ["UNICODE", "Unicode", "unicode"]
DEFAULT_TEKLA_DIRS = [REPO / "V_pru" / "app" / "data", REPO / "V_num" / "app" / "data"]


# ---------------------------------------------------------------------------
# Lectura del CSV -> filas en formato CODAME (54 columnas)
# ---------------------------------------------------------------------------
def _pick(row, *names):
    for n in names:
        if n in row and pd.notna(row[n]):
            return row[n]
    return None


def _load_profile_lookup(tekla_dir: Path):
    """Perfiles de BEAM/COLUMN -> BEAM_tf_mm (de tekla_eu.csv + tekla_cad.csv)."""
    look = {}
    for f in ["tekla_eu.csv", "tekla_cad.csv"]:
        p = Path(tekla_dir) / f
        if p.exists():
            d = pd.read_csv(p)
            for _, r in d.iterrows():
                look[str(r["tekla_nomenclature_1"])] = r
    return look


def rows_from_dataframe(df: pd.DataFrame, tekla_dir: Path | None = None) -> list[dict]:
    """Convierte un DataFrame (salida de V_pru) en lista de filas {columna_excel: valor}."""
    if tekla_dir is None:
        tekla_dir = next((d for d in DEFAULT_TEKLA_DIRS if d.exists()), None)
    look = _load_profile_lookup(tekla_dir) if tekla_dir else {}

    rows = []
    for _, r in df.iterrows():
        grado = _pick(r, "grado_acero", "AceroEstructural")
        clase = _pick(r, "clase_tornillo", "EstandarTornillos")
        inp = {
            "UNICODE": _pick(r, *UNICODE_ALIASES),
            "BEAM": _pick(r, "BEAM", "beam"),
            "COLUMN": _pick(r, "COLUMN", "column"),
            "Capacity_Moment": _pick(r, "Capacity_Moment"),
            "Capacity_Shear": _pick(r, "Capacity_Shear"),
            "Capacity_Axial": _pick(r, "Capacity_Axial"),
            "Capacity_Moment_Percentage": _pick(r, "Capacity_Moment_Percentage"),
            "Capacity_Shear_Percentage": _pick(r, "Capacity_Shear_Percentage"),
            "Capacity_Axial_Percentage": _pick(r, "Capacity_Axial_Percentage"),
            "grado_acero": grado,
            "clase_tornillo": str(clase) if clase is not None else None,
        }
        design = {c: _pick(r, c) for c in
                  ["standard", "Bolt", "SlipCritical", "g", "e", "d", "Bp", "tp", "Lh",
                   "p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9", "p10", "p11", "p12",
                   "tws", "ts", "tbs", "tst", "n_alma", "n_cantonera"]}
        feats = {
            "BEAM_tf_mm": _pick(r, "BEAM_tf_mm"),
            "fy_acero_mpa": _pick(r, "fy_acero_mpa"),
            "fu_acero_mpa": _pick(r, "fu_acero_mpa"),
        }
        # rellenar feats que falten
        beam = inp["BEAM"]
        if (feats["BEAM_tf_mm"] is None) and beam is not None and str(beam) in look:
            feats["BEAM_tf_mm"] = look[str(beam)].get("tf_mm")
        if feats["fy_acero_mpa"] is None and grado in ACERO_TABLE:
            feats["fy_acero_mpa"], feats["fu_acero_mpa"] = ACERO_TABLE[grado]

        rows.append(model_to_row(inp, design, feats))
    return rows


# ---------------------------------------------------------------------------
# Excel COM
# ---------------------------------------------------------------------------
def _as_2d(val):
    if val is None:
        return []
    if not isinstance(val, tuple):
        return [[val]]
    if len(val) == 0:
        return []
    if isinstance(val[0], tuple):
        return [list(r) for r in val]
    return [list(val)]


def _get_excel():
    try:
        return win32.GetActiveObject("Excel.Application"), False
    except Exception:
        app = win32.DispatchEx("Excel.Application")
        app.Visible = False
        app.DisplayAlerts = False
        return app, True


def _pick_workbook(app, name_substr):
    books = list(app.Workbooks)
    if not books:
        raise RuntimeError("No hay libros abiertos en Excel.")
    if name_substr:
        for wb in books:
            if name_substr.lower() in wb.Name.lower():
                return wb
        raise RuntimeError(f"Ningun libro abierto contiene '{name_substr}'. Abiertos: {[b.Name for b in books]}")
    return books[0]


def _find_table(wb, sheet_name, table_name):
    ws = wb.Worksheets(sheet_name)
    for t in ws.ListObjects:
        if t.Name == table_name:
            return ws, t
    raise KeyError(f"No existe la tabla '{table_name}' en '{sheet_name}'")


def _header_index(table):
    hdr = table.HeaderRowRange.Value
    if isinstance(hdr, tuple) and hdr and isinstance(hdr[0], tuple):
        hdr = hdr[0]
    elif not isinstance(hdr, tuple):
        hdr = (hdr,)
    return {str(h): i + 1 for i, h in enumerate(hdr)}


def _write_block(table, rows_values, idx):
    ncols = max(idx.values())
    arr = []
    for values in rows_values:
        row = [None] * ncols
        for name, v in values.items():
            c = idx.get(name)
            if c:
                row[c - 1] = v
        arr.append(row)
    start = table.DataBodyRange.Cells(1, 1)
    start.Resize(len(arr), ncols).Value = arr


def _read_rows(table):
    idx = _header_index(table)
    inv = {c: n for n, c in idx.items()}
    headers = [inv[i] for i in range(1, max(idx.values()) + 1)]
    rows = _as_2d(table.DataBodyRange.Value)
    return headers, rows


def _run_exe(exe, workbook_name, table_address, timeout=1800, log=print):
    args = [str(exe), ACCION, workbook_name, table_address, "$A$1",
            TABLE_MOMENT, OBJ_MAPEO, OBJ_CALC]
    log(f"Ejecutando: {' '.join(args)}")
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if p.stderr.strip():
        log(f"stderr exe: {p.stderr.strip()[:300]}")
    return p.returncode


# ---------------------------------------------------------------------------
# API principal
# ---------------------------------------------------------------------------
def validate_rows(rows_values, unicodes, workbook_name=DEFAULT_WORKBOOK_NAME, exe=DEFAULT_EXE,
                  workbook_path=None, chunk=200, dry_run=False, timeout=1800, log=print):
    """Ejecuta CODAME sobre filas ya traducidas. Devuelve (ratio_headers, resultados).

    resultados: lista de (unicode, estado, ratios_dict, comp_dict).
    """
    exe = Path(exe)
    app = created = None
    results, ratio_headers = [], None
    try:
        app, created = _get_excel()
        try:
            wb = _pick_workbook(app, workbook_name)
        except Exception:
            if not workbook_path:
                raise
            wb = app.Workbooks.Open(str(Path(workbook_path).resolve()),
                                    UpdateLinks=0, ReadOnly=False,
                                    IgnoreReadOnlyRecommended=True, AddToMru=False)
        wb.Activate()
        _, t_moment = _find_table(wb, SHEET_MOMENT, TABLE_MOMENT)
        idx = _header_index(t_moment)
        original = t_moment.DataBodyRange.Value

        def row_dict(headers, values):
            return {h: (values[i] if i < len(values) else None) for i, h in enumerate(headers)}

        i = 0
        while i < len(rows_values):
            batch = rows_values[i:i + chunk]
            t_moment.DataBodyRange.ClearContents()
            _write_block(t_moment, batch, idx)
            wb.Worksheets(SHEET_MOMENT).Activate()
            if not dry_run:
                _run_exe(exe, wb.Name, t_moment.Range.Address, timeout=timeout, log=log)
            _, t_rat = _find_table(wb, SHEET_MOMENT, TABLE_RATIOS)
            _, t_comp = _find_table(wb, SHEET_MOMENT, TABLE_COMPLEMEN)
            rh, rrows = _read_rows(t_rat)
            ch, crows = _read_rows(t_comp)
            if ratio_headers is None:
                ratio_headers = rh
            k = min(len(rrows), len(batch))
            for j in range(k):
                results.append((unicodes[i + j], "ok", row_dict(rh, rrows[j]), row_dict(ch, crows[j])))
            if k < len(batch):
                results.append((unicodes[i + k], "FAILED", {}, {}))
                i = i + k + 1
            else:
                i += len(batch)
            log(f"  {min(i, len(rows_values))}/{len(rows_values)} procesadas")

        # restaurar
        t_moment.DataBodyRange.ClearContents()
        b2 = _as_2d(original)
        if b2:
            t_moment.DataBodyRange.Cells(1, 1).Resize(len(b2), len(b2[0])).Value = b2
    finally:
        if created and app is not None:
            try:
                app.Quit()
            except Exception:
                pass
    return ratio_headers, results


def validate_csv(csv_path, out_csv=None, workbook_name=DEFAULT_WORKBOOK_NAME, workbook_path=None,
                 exe=DEFAULT_EXE, chunk=200, dry_run=False, tekla_dir=None, timeout=1800, log=print):
    """Valida un CSV de disenos con CODAME. Devuelve un DataFrame [Unicode, Estado, ratios...]."""
    df = pd.read_csv(csv_path, sep=None, engine="python")
    unicodes = df[[c for c in UNICODE_ALIASES if c in df.columns][0]] if any(c in df.columns for c in UNICODE_ALIASES) else df.index
    rows = rows_from_dataframe(df, tekla_dir=tekla_dir)
    if workbook_path is None:
        workbook_path = _default_workbook_path()

    ratio_headers, results = validate_rows(rows, list(unicodes), workbook_name=workbook_name,
                                           exe=exe, workbook_path=workbook_path, chunk=chunk,
                                           dry_run=dry_run, timeout=timeout, log=log)

    data = []
    for unicode, estado, d, c in results:
        rec = {"Unicode": unicode, "Estado": estado}
        for h in (ratio_headers or []):
            v = d.get(h)
            rec[h] = np.nan if v == SENTINEL else v
        rp = c.get("RatioPesimo")
        rec["RatioPesimo"] = np.nan if rp == SENTINEL else rp
        rec["DescripRatioPesimo"] = c.get("DescripRatioPesimo")
        data.append(rec)
    out = pd.DataFrame(data)
    if out_csv:
        out.to_csv(out_csv, index=False)
        log(f"Escrito {out_csv}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Valida disenos (CSV) con CODAME.")
    ap.add_argument("--csv", required=True, help="CSV de disenos (salida de V_pru)")
    ap.add_argument("--out", help="CSV de salida con los ratios")
    ap.add_argument("--workbook-name", default=DEFAULT_WORKBOOK_NAME)
    ap.add_argument("--workbook-path", help="abrir este .xlsm si no hay ninguno abierto")
    ap.add_argument("--exe", default=str(DEFAULT_EXE))
    ap.add_argument("--chunk", type=int, default=200)
    ap.add_argument("--tekla-dir", default=None)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    def log(m):
        print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

    out = validate_csv(args.csv, out_csv=args.out, workbook_name=args.workbook_name,
                       workbook_path=args.workbook_path, exe=args.exe, chunk=args.chunk,
                       dry_run=args.dry_run, tekla_dir=args.tekla_dir, timeout=args.timeout, log=log)
    ok = (out["Estado"] == "ok").sum() if len(out) else 0
    log(f"TOTAL: {ok} ok / {(out['Estado']!='ok').sum() if len(out) else 0} fallidas / {len(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
