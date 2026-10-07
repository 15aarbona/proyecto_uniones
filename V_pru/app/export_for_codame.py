r"""
Predice con el modelo de V_num y exporta un `model.json` listo para
`production/validation/validate_codame.py --model-json`.

Ejecutar DESDE V_num/app (para que `import store` y `core.*` resuelvan):

    python export_for_codame.py --input caso.csv --out ..\..\model.json
    python export_for_codame.py --input caso.csv --out model.json --index 0

`caso.csv` debe traer las columnas de produccion:
    UNICODE, BEAM, COLUMN, Capacity_Moment, Capacity_Shear, Capacity_Axial,
    grado_acero, clase_tornillo
(opcionalmente las *_Percentage para MzEd/FyEd/FxEd_Porcen del libro).

El JSON resultante tiene la forma:
    {"input": {...}, "design": {...}, "feats": {...}}
"""
import argparse
import json
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402  (V_num/app/store.py)


def jsonable(v):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (int, float)):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return v
    if hasattr(v, "item"):
        try:
            return jsonable(v.item())
        except Exception:
            pass
    if isinstance(v, bool):
        return v
    return str(v) if not isinstance(v, str) else v


def row_to_dict(row):
    return {str(k): jsonable(v) for k, v in row.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="CSV con una o mas filas de entrada")
    ap.add_argument("--out", required=True, help="fichero model.json de salida")
    ap.add_argument("--index", type=int, default=0, help="fila del CSV a exportar")
    ap.add_argument("--sep", default=None, help="separador del CSV (por defecto autodetecta)")
    args = ap.parse_args()

    df = pd.read_csv(
        args.input,
        sep=args.sep,
        engine="python" if args.sep is None else "c",
        dtype={"BEAM": str, "COLUMN": str, "UNICODE": str,
               "grado_acero": str, "clase_tornillo": str},
    )
    if args.index >= len(df):
        sys.exit(f"index {args.index} fuera de rango (filas={len(df)})")

    result, feats = store.predict_df(df)
    payload = {
        "input": row_to_dict(df.iloc[args.index]),
        "design": row_to_dict(result.iloc[args.index]),
        "feats": row_to_dict(feats.iloc[args.index]),
    }
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"Escrito {args.out} (fila {args.index})")
    print("Siguiente:")
    print(f'  production\\validation\\run_validate_netonly.cmd <DOMINIO\\usuario> --row 1 --model-json "{args.out}"')


if __name__ == "__main__":
    main()
