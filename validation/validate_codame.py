"""
Validacion de un diseno de momento con CODAME (CalcCodame.exe), sin tocar Excel a mano.

IMPORTANTE (por que no usa una copia oculta):
  CalcCodame.exe se engancha a la instancia de Excel en ejecucion mediante COM
  (GetActiveObject). Por tanto hay que trabajar SOBRE LA MISMA INSTANCIA y el MISMO
  libro que el exe va a encontrar. Este script:
    1. Se conecta a la instancia de Excel ya abierta (o crea una si no hay ninguna).
    2. Selecciona el libro objetivo (por defecto, el que contenga 'CONNEXTOR').
    3. Escribe el diseno en Tabla_MOMENT_M1 (hoja IM_MOMENT) si se pasa --values/--model-json.
    4. Lanza CalcCodame.exe.
    5. Lee los resultados (TResultadosComplemen / TResultadosRatios) y los devuelve en JSON.

La contrasena NUNCA se maneja aqui: lanzar bajo `runas /netonly` para que la
autenticacion de red use la cuenta de dominio.

Uso:
  python validate_codame.py --row 1
  python validate_codame.py --row 1 --model-json model.json
  python validate_codame.py --row 1 --model-json model.json --dry-run
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import win32com.client as win32

# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parents[2]
DEFAULT_EXE = REPO / "CalcCodame" / "CalcCodame.exe"

SHEET_MOMENT = "IM_MOMENT"
TABLE_MOMENT = "Tabla_MOMENT_M1"
TABLE_RATIOS = "TResultadosRatios"
TABLE_COMPLEMEN = "TResultadosComplemen"

ACCION = "CALCULAR_CODAME"
OBJ_MAPEO = "CodigoMOMENTAgregadorCODAME0"   # hoja ObjetosTablaCodame, fila IM_MOMENT, col B
OBJ_CALC = "MOMENT_CODAMEaux"                # hoja ObjetosTablaCodame, fila IM_MOMENT, col C


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def get_excel():
    """Devuelve (app, created). Reutiliza la instancia abierta; si no hay, crea una."""
    try:
        app = win32.GetActiveObject("Excel.Application")
        return app, False
    except Exception:
        app = win32.DispatchEx("Excel.Application")
        app.Visible = False
        app.DisplayAlerts = False
        return app, True


def pick_workbook(app, name_substr):
    books = list(app.Workbooks)
    if not books:
        raise RuntimeError("No hay libros abiertos en Excel.")
    if name_substr:
        for wb in books:
            if name_substr.lower() in wb.Name.lower():
                return wb
        raise RuntimeError(
            f"Ningun libro abierto contiene '{name_substr}'. Abiertos: {[b.Name for b in books]}"
        )
    # sin filtro: preferir el activo; si no, el primero
    try:
        if app.ActiveWorkbook is not None:
            return app.ActiveWorkbook
    except Exception:
        pass
    return books[0]


def find_table(wb, sheet_name, table_name):
    ws = wb.Worksheets(sheet_name)
    for t in ws.ListObjects:
        if t.Name == table_name:
            return ws, t
    raise KeyError(f"No existe la tabla '{table_name}' en '{sheet_name}'")


def header_index(table):
    hdr = table.HeaderRowRange.Value
    if isinstance(hdr, tuple) and hdr and isinstance(hdr[0], tuple):
        hdr = hdr[0]
    elif not isinstance(hdr, tuple):
        hdr = (hdr,)
    return {str(h): i + 1 for i, h in enumerate(hdr)}


def write_values(table, data_row, values):
    idx = header_index(table)
    unknown = [k for k in values if k not in idx]
    if unknown:
        log(f"AVISO: columnas no encontradas (se ignoran): {unknown}")
    for col, val in values.items():
        if col in idx:
            table.DataBodyRange.Cells(data_row, idx[col]).Value = val


def read_row(table, data_row):
    idx = header_index(table)
    return {name: table.DataBodyRange.Cells(data_row, c).Value for name, c in idx.items()}


def run_codame(exe, workbook_name, table_address, mensaje_address, table_name, timeout=180):
    args = [str(exe), ACCION, workbook_name, table_address, mensaje_address,
            table_name, OBJ_MAPEO, OBJ_CALC]
    log(f"Ejecutando: {' '.join(args)}")
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if p.stdout.strip():
        log(f"stdout exe: {p.stdout.strip()[:500]}")
    if p.stderr.strip():
        log(f"stderr exe: {p.stderr.strip()[:500]}")
    log(f"exe exit={p.returncode}")
    return p.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=str(DEFAULT_EXE))
    ap.add_argument("--workbook-name", default="CONNEXTOR", help="subcadena del libro abierto a usar")
    ap.add_argument("--row", type=int, default=1, help="fila de datos (1-based) en la tabla")
    ap.add_argument("--values", help="JSON {columna_excel: valor}")
    ap.add_argument("--model-json", help="JSON {input,design,feats} del modelo")
    ap.add_argument("--out", help="fichero JSON de salida")
    ap.add_argument("--dry-run", action="store_true", help="no lanza el exe")
    args = ap.parse_args()

    exe = Path(args.exe).resolve()
    if not exe.exists():
        sys.exit(f"No existe el exe: {exe}")

    result = {"ok": False, "row": args.row, "workbook": None, "excel_mode": None,
              "resultados": {}, "ratios": {}, "error": None}
    app = None
    created = False
    try:
        app, created = get_excel()
        result["excel_mode"] = "new" if created else "existing"
        log(f"Excel: instancia {'nueva' if created else 'existente'}; libros abiertos: {[b.Name for b in app.Workbooks]}")

        wb = pick_workbook(app, args.workbook_name)
        result["workbook"] = wb.Name
        log(f"Libro objetivo: {wb.Name}")
        wb.Activate()

        _, t_moment = find_table(wb, SHEET_MOMENT, TABLE_MOMENT)
        wb.Worksheets(SHEET_MOMENT).Activate()

        if args.values or args.model_json:
            values = {}
            if args.model_json:
                from model_to_row import model_to_row
                mj = json.loads(Path(args.model_json).read_text(encoding="utf-8-sig"))
                values.update(model_to_row(mj.get("input", {}), mj.get("design", {}), mj.get("feats", {})))
                log(f"Traducido modelo -> {len(values)} columnas de Excel")
            if args.values:
                values.update(json.loads(Path(args.values).read_text(encoding="utf-8-sig")))
            write_values(t_moment, args.row, values)
            log(f"Escritos {len(values)} valores en la fila {args.row} de {TABLE_MOMENT}")

        if not args.dry_run:
            try:
                wb.Worksheets(SHEET_MOMENT).Activate()
                t_moment.DataBodyRange.Cells(args.row, 1).Select()
            except Exception as e:
                log(f"(no se pudo seleccionar la fila objetivo: {e})")
            run_codame(exe, wb.Name, t_moment.Range.Address, "$A$1", TABLE_MOMENT)

        _, t_comp = find_table(wb, SHEET_MOMENT, TABLE_COMPLEMEN)
        _, t_rat = find_table(wb, SHEET_MOMENT, TABLE_RATIOS)
        result["diseno"] = read_row(t_moment, args.row)
        result["resultados"] = read_row(t_comp, args.row)
        result["ratios"] = read_row(t_rat, args.row)
        rp = result["resultados"].get("RatioPesimo")
        result["ratio_pesimo"] = rp
        result["descrip_ratio_pesimo"] = result["resultados"].get("DescripRatioPesimo")
        try:
            result["ok"] = float(rp) <= 1.0
        except (TypeError, ValueError):
            result["ok"] = None
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        log(f"ERROR: {result['error']}")
    finally:
        # Solo se cierra Excel si lo hemos creado nosotros (no la instancia del usuario).
        if created and app is not None:
            try:
                app.Quit()
            except Exception:
                pass

    payload = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        log(f"Resultado en {args.out}")
    else:
        print(payload)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
