"""
Reemplaza model_store/global_dataset.parquet por la estructura nueva (v4, esquema de
data/train_v3.parquet + Capacity_* + n_alma/n_cantonera), a partir de los parquet ricos
data/train_v2.parquet y data/test_v2.parquet (alineados fila a fila con v3, verificado).

Uso:  python rebuild_global.py [train_rico.parquet test_rico.parquet]
"""
import sys
from pathlib import Path

import pandas as pd

import store
from core.dataset import ys_from_p
from core.config import Y_COLUMNS

if __name__ == "__main__":
    data_dir = Path(r"C:\Users\jabal\OtrosProyectos\proyecto_uniones\data")
    if len(sys.argv) == 3:
        paths = [Path(p) for p in sys.argv[1:3]]
    else:
        paths = [data_dir / "train_v2.parquet", data_dir / "test_v2.parquet"]

    for p in paths:
        if not p.exists():
            raise SystemExit(f"No existe {p}")

    old = store.load_global_dataset()
    if old is not None:
        print(f"Dataset global ANTIGUO: {len(old)} filas, {len(old.columns)} columnas")
        print("  columnas:", list(old.columns)[:8], "...")

    global_df = store.rebuild_global_dataset(paths)

    print(f"\nDataset global NUEVO: {len(global_df)} filas, {len(global_df.columns)} columnas")
    print("  columnas:", list(global_df.columns))
    print("\nChequeos de coherencia:")
    Y = ys_from_p(global_df)[Y_COLUMNS]
    nY = (Y > 0).sum(axis=1)
    print(f"  #Ys == n_alma + n_cantonera + 1 (Y derivadas de p): "
          f"{(nY == global_df['n_alma'] + global_df['n_cantonera'] + 1).all()}")
    print(f"  Lh >= 0                          : {(global_df['Lh'] >= 0).all()}")
    print(f"  n_alma rango                     : {global_df['n_alma'].min()}..{global_df['n_alma'].max()}")
    print(f"  n_cantonera rango                : {global_df['n_cantonera'].min()}..{global_df['n_cantonera'].max()}")
    print(f"  standard                         : {global_df['standard'].nunique()} valores")
    print(f"  Bolt                             : {sorted(global_df['Bolt'].unique())}")
    print("\nGuardado en:", store.GLOBAL_DATASET_PATH)
