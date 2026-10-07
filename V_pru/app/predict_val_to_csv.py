"""
Genera un CSV con las PREDICCIONES del modelo V_pru sobre el conjunto de validacion,
listo para pasarlo a `validation.codame.validate_csv`.

- Reproduce el split de entrenamiento: train_test_split(df, test_size=0.2, random_state=2).
- Usa SOLO las columnas de entrada (pobres) del test y llama a store.predict_df.
- Escribe: input + diseno predicho + feats (BEAM_tf_mm, fy_acero_mpa, fu_acero_mpa).

Uso (desde V_pru/app):
    python predict_val_to_csv.py [salida.csv]
"""
import sys
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

import store

CSV_PATH = store.DATA_DIR / "data_final.csv"


def _tekla_paths():
    """Rutas a los catalogos Tekla (eu, cad, faltante). Usa los de V_pru/app/data si
    estan los 3; si falta alguno, cae a V_num/app/data (que si los tiene)."""
    names = ["tekla_eu.csv", "tekla_cad.csv", "tekla_faltante.csv"]
    local = [store.DATA_DIR / n for n in names]
    if all(p.exists() for p in local):
        return tuple(local)
    repo = store.APP_DIR.parents[1]
    vnum = repo / "V_num" / "app" / "data"
    return tuple(vnum / n for n in names)


def main(out_path: Path):
    df = pd.read_csv(CSV_PATH, sep=";")
    df = df.loc[:, [c for c in df.columns if not str(c).startswith("Unnamed")]]

    # split identico al entrenamiento (mismo tamano y semilla)
    _, test = train_test_split(df, test_size=0.2, random_state=2)
    test = test.reset_index(drop=True)

    input_df = pd.DataFrame({
        "UNICODE": [f"VAL-{i:05d}" for i in range(len(test))],
        "BEAM": test["BEAM"].values,
        "COLUMN": test["COLUMN"].values,
        "Capacity_Moment": test["Capacity_Moment"].values,
        "Capacity_Shear": test["Capacity_Shear"].values,
        "Capacity_Axial": test["Capacity_Axial"].values,
        "Capacity_Moment_Percentage": test["Capacity_Moment_Percentage"].values,
        "Capacity_Shear_Percentage": test["Capacity_Shear_Percentage"].values,
        "Capacity_Axial_Percentage": test["Capacity_Axial_Percentage"].values,
        "grado_acero": test["AceroEstructural"].astype(str).values,
        "clase_tornillo": test["EstandarTornillos"].astype(str).values,
    })

    result, feats = store.predict_df(input_df, tekla_paths=_tekla_paths())

    # quitar ids duplicados del design y anexar feats necesarias
    design = result.drop(columns=["UNICODE", "BEAM", "COLUMN"], errors="ignore").reset_index(drop=True)
    feats_sel = feats[[c for c in ["BEAM_tf_mm", "fy_acero_mpa", "fu_acero_mpa"] if c in feats.columns]].reset_index(drop=True)

    out = pd.concat([input_df.reset_index(drop=True), design, feats_sel], axis=1)
    out.to_csv(out_path, index=False)
    print(f"Escrito {out_path}: {len(out)} filas, {len(out.columns)} columnas")


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else (store.APP_DIR / "val_predicciones.csv")
    main(out)
