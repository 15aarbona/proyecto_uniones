"""
Entrenamiento del modelo (v3: E-S/D_i/I-C/C_i/E-C en vez de p1..p12).

MODO NORMAL:
    python train.py --train_path data/train.parquet --test_path data/test.parquet

MODO SMOKE TEST (solo con test.parquet; split interno, NO es un modelo de producción):
    python train.py --smoke_test --test_path test.parquet
"""
import argparse
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader
from sklearn.model_selection import train_test_split

from lookups import build_profile_lookup_from_df, build_profile_lookup_from_tekla_csvs, check_profile_coverage
from dataset import Preprocessor, ConnectionDataset, add_geometry_targets
from model import ConnectionDesignNet
from losses import ConnectionDesignLoss
from training import fit, predict_loader, outputs_to_design
from evaluation import (preparar_para_evaluar, evaluar_predicciones, evaluar_estructura,
                        verificar_reversibilidad)


def prepare_raw_equivalent(df: pd.DataFrame) -> pd.DataFrame:
    """
    Nombres de columna del input real (grado_acero / clase_tornillo). Las clases de DrawingCode
    con <20 muestras se agrupan en "OTHER" (siguen desbalanceadas incluso con el dataset completo).
    """
    df = df.rename(columns={"AceroEstructural": "grado_acero", "EstandarTornillos": "clase_tornillo"})
    counts = df["DrawingCode"].value_counts()
    rare = counts[counts < 20].index
    if len(rare) > 0:
        df["DrawingCode"] = df["DrawingCode"].where(~df["DrawingCode"].isin(rare), "OTHER")
    return df


def run(args):
    torch.manual_seed(42)
    np.random.seed(42)

    full = prepare_raw_equivalent(pd.read_parquet(args.test_path))

    if args.smoke_test or args.train_path is None:
        print(f"[smoke test] usando solo {args.test_path} ({len(full)} filas) con split interno.")
        train_df, temp_df = train_test_split(full, test_size=0.30, random_state=42)
        val_df, test_df = train_test_split(temp_df, test_size=0.50, random_state=42)
    else:
        train_full = prepare_raw_equivalent(pd.read_parquet(args.train_path))
        train_df, val_df = train_test_split(train_full, test_size=0.15, random_state=42)
        test_df = full

    if args.tekla_eu and args.tekla_cad and args.tekla_faltante:
        profile_lookup = build_profile_lookup_from_tekla_csvs(args.tekla_eu, args.tekla_cad, args.tekla_faltante)
        print(f"Tabla de perfiles cargada desde catálogos Tekla: {len(profile_lookup)} perfiles.")
    else:
        profile_lookup = build_profile_lookup_from_df(pd.concat([train_df, val_df, test_df]))
        print(f"[aviso] usando fallback de perfiles derivado de train/test ({len(profile_lookup)} perfiles).")

    needed = set()
    for d in (train_df, val_df, test_df):
        needed |= set(d["BEAM"]) | set(d["COLUMN"])
    missing = check_profile_coverage(needed, profile_lookup)
    if missing:
        raise KeyError(f"Faltan {len(missing)} perfiles en la tabla de lookup: {missing}")

    # p1..p12 -> E-S, D_1..5, I-C, C_1..5, E-C. Se comprueba antes de entrenar que la
    # descomposición no pierde información (incluida la extracción de C_i, sin columna real).
    print("Verificación de reversibilidad p <-> geometría con nombre (en train):")
    verificar_reversibilidad(train_df)
    train_df, val_df, test_df = (add_geometry_targets(d) for d in (train_df, val_df, test_df))

    pre = Preprocessor().fit(train_df)

    train_ds, val_ds, test_ds = (ConnectionDataset(d, pre) for d in (train_df, val_df, test_df))
    train_loader = DataLoader(train_ds, batch_size=64, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=128, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=128, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = ConnectionDesignNet(
        cat_cardinalities=pre.cat_cardinalities,
        num_continuous=len(pre.num_scaler.mean_),
        n_drawing_codes=pre.n_drawing_codes,
    ).to(device)

    history = fit(model, train_loader, val_loader, ConnectionDesignLoss(), device,
                  epochs=args.epochs, lr=args.lr)

    # ---- evaluación en test ----
    outputs = predict_loader(model, test_loader, device)
    full_design = outputs_to_design(outputs, pre, reconstruct_p=True)

    print("\n--- Clasificación ---")
    for col in ("DrawingCode", "Bolt", "SlipCritical"):
        acc = (full_design[col].values == test_df[col].astype(str).values).mean()
        print(f"Accuracy {col:<13}: {acc:.3f}")

    df_real, df_pred = preparar_para_evaluar(test_df, full_design)
    evaluar_predicciones(df_real, df_pred)
    evaluar_estructura(test_df, full_design)

    torch.save(model.state_dict(), args.out)
    print(f"\nModelo guardado en {args.out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train_path", type=str, default=None)
    parser.add_argument("--test_path", type=str, required=True)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--lr", type=float, default=2e-3)
    parser.add_argument("--out", type=str, default="model.pt")
    parser.add_argument("--smoke_test", action="store_true")
    parser.add_argument("--tekla_eu", type=str, default=None)
    parser.add_argument("--tekla_cad", type=str, default=None)
    parser.add_argument("--tekla_faltante", type=str, default=None)
    run(parser.parse_args())
