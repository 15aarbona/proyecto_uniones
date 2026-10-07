"""
Reemplaza model_store/global_dataset.parquet por la estructura nueva a partir de
V_pru/app/data/data_final.csv (sep=';').

Uso:  python rebuild_global.py [data_final.csv]
"""
import sys
from pathlib import Path

import pandas as pd

import store

if __name__ == "__main__":
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (store.DATA_DIR / "data_final.csv")
    if not csv_path.exists():
        raise SystemExit(f"No existe {csv_path}")

    old = store.load_global_dataset()
    if old is not None:
        print(f"Dataset global ANTIGUO: {len(old)} filas, {len(old.columns)} columnas")

    global_df = store.build_global_structure_from_final(pd.read_csv(csv_path, sep=";"))

    store.STORE_DIR.mkdir(parents=True, exist_ok=True)
    global_df.to_parquet(store.GLOBAL_DATASET_PATH, index=False)

    print(f"\nDataset global NUEVO: {len(global_df)} filas, {len(global_df.columns)} columnas")
    print("  columnas:", list(global_df.columns))
    print("\nChequeos de coherencia:")
    print(f"  n_alma rango       : {global_df['n_alma'].min()}..{global_df['n_alma'].max()}")
    print(f"  n_cantonera rango  : {global_df['n_cantonera'].min()}..{global_df['n_cantonera'].max()}")
    print(f"  Lh >= 0            : {(global_df['Lh'] >= 0).all()}")
    print(f"  standard           : {global_df['standard'].nunique()} valores")
    print(f"  Bolt               : {sorted(global_df['Bolt'].unique())}")
    print("\nGuardado en:", store.GLOBAL_DATASET_PATH)
