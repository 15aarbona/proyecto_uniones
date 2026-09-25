"""
Capa de orquestación entre las GUIs (Streamlit) y el pipeline ya existente
(core/ = config.py, dataset.py, geometry.py, lookups.py, losses.py, model.py,
postprocess.py, training.py, evaluation.py, sin cambios de lógica).

Responsabilidades:
  - Guardar / cargar el "bundle" del modelo: pesos (model.pt), preprocesador
    ajustado (preprocessor.pkl) y metadatos (metadata.json).
  - Guardar / cargar el DATASET GLOBAL (model_store/global_dataset.parquet):
    el dataframe YA preparado para entrenar (con BEAM_*/COLUMN_* de lookup,
    fy/fu, y la geometría con nombre E-S/D_i/I-C/C_i/E-C vía
    dataset.add_geometry_targets). Es la fuente de verdad para reentrenar.
  - train_initial(): primer entrenamiento a partir de train.parquet/test.parquet
    (el formato "rico" que ya se usaba). Crea el dataset global = train+val+test.
  - retrain(): reentrena DESDE CERO usando el dataset global acumulado
    (que puede incluir filas nuevas validadas por el usuario).
  - predict_df(): inferencia sobre un CSV "pobre" tipo fictional.csv.
  - build_dataset_rows() / append_validated_rows(): una vez el usuario valida
    predicciones, se ensamblan como filas con el mismo esquema del dataset
    global y se añaden (se guardan, no se reentrena automáticamente).
"""
import json
import pickle
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader
from sklearn.model_selection import train_test_split

from core.lookups import (
    build_profile_lookup_from_tekla_csvs, check_profile_coverage, build_training_features,
)
from core.dataset import Preprocessor, ConnectionDataset, add_geometry_targets
from core.model import ConnectionDesignNet
from core.losses import ConnectionDesignLoss
from core.training import fit, predict_loader, outputs_to_design, forward_numpy
from core.evaluation import preparar_para_evaluar, evaluar_predicciones

APP_DIR = Path(__file__).parent
STORE_DIR = APP_DIR / "model_store"
DATA_DIR = APP_DIR / "data"

MODEL_PATH = STORE_DIR / "model.pt"
PREPROCESSOR_PATH = STORE_DIR / "preprocessor.pkl"
METADATA_PATH = STORE_DIR / "metadata.json"
GLOBAL_DATASET_PATH = STORE_DIR / "global_dataset.parquet"
HISTORY_PATH = STORE_DIR / "training_history.json"

DEFAULT_TEKLA_PATHS = (DATA_DIR / "tekla_eu.csv", DATA_DIR / "tekla_cad.csv", DATA_DIR / "tekla_faltante.csv")

ID_COLUMNS = ["UNICODE", "BEAM", "COLUMN"]


# ---------------------------------------------------------------------------
# Utilidades de estado
# ---------------------------------------------------------------------------

def model_exists() -> bool:
    return MODEL_PATH.exists() and PREPROCESSOR_PATH.exists() and METADATA_PATH.exists()


def load_metadata() -> dict | None:
    if METADATA_PATH.exists():
        return json.loads(METADATA_PATH.read_text())
    return None


def load_history() -> list:
    if HISTORY_PATH.exists():
        return json.loads(HISTORY_PATH.read_text())
    return []


def load_global_dataset() -> pd.DataFrame | None:
    if GLOBAL_DATASET_PATH.exists():
        return pd.read_parquet(GLOBAL_DATASET_PATH)
    return None


def _device():
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def prepare_raw_equivalent(df: pd.DataFrame, rare_threshold: int = 20) -> pd.DataFrame:
    """Igual que en train.py: renombra columnas y agrupa DrawingCode raros en OTHER."""
    df = df.rename(columns={"AceroEstructural": "grado_acero", "EstandarTornillos": "clase_tornillo"})
    counts = df["DrawingCode"].value_counts()
    rare = counts[counts < rare_threshold].index
    if len(rare) > 0:
        df["DrawingCode"] = df["DrawingCode"].where(~df["DrawingCode"].isin(rare), "OTHER")
    return df


def _build_model(pre: Preprocessor, device) -> ConnectionDesignNet:
    return ConnectionDesignNet(
        cat_cardinalities=pre.cat_cardinalities,
        num_continuous=len(pre.num_scaler.mean_),
        n_drawing_codes=pre.n_drawing_codes,
    ).to(device)


def _compute_metrics(test_df: pd.DataFrame, full_design: pd.DataFrame) -> dict:
    cls_acc = {}
    for col in ("DrawingCode", "Bolt", "SlipCritical"):
        cls_acc[col] = float((full_design[col].values == test_df[col].astype(str).values).mean())

    df_real, df_pred = preparar_para_evaluar(test_df, full_design)
    df_res = evaluar_predicciones(df_real, df_pred)

    return {
        "n_test": int(len(test_df)),
        "classification_accuracy": cls_acc,
        "regression_table": df_res.to_dict(orient="records"),
    }


def _save_bundle(model, pre: Preprocessor, global_df: pd.DataFrame, metrics: dict,
                  epochs: int, lr: float, mode: str) -> dict:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), MODEL_PATH)
    with open(PREPROCESSOR_PATH, "wb") as f:
        pickle.dump(pre, f)
    global_df.to_parquet(GLOBAL_DATASET_PATH, index=False)

    meta = {
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,  # "initial" | "retrain"
        "epochs": epochs,
        "lr": lr,
        "n_rows_dataset": int(len(global_df)),
        "cat_cardinalities": pre.cat_cardinalities,
        "n_drawing_codes": pre.n_drawing_codes,
        "drawing_code_classes": list(pre.drawing_code_encoder.classes_),
        "metrics": metrics,
    }
    METADATA_PATH.write_text(json.dumps(meta, indent=2, default=str))

    hist = load_history()
    hist.append(meta)
    HISTORY_PATH.write_text(json.dumps(hist, indent=2, default=str))
    return meta


# ---------------------------------------------------------------------------
# Entrenamiento inicial
# ---------------------------------------------------------------------------

def train_initial(test_path, train_path=None, epochs=150, lr=2e-3, tekla_paths=None) -> dict:
    """
    Primer entrenamiento, igual que train.py. test_path es obligatorio (formato
    train/test.parquet ya "rico", con p1..p12, DrawingCode, Bolt, etc.).
    Si no se pasa train_path, hace split interno de test_path (modo smoke test).
    Al terminar, guarda el bundle del modelo Y crea el dataset global
    (train_df + val_df + test_df, ya con geometría con nombre) para reentrenos futuros.
    """
    torch.manual_seed(42)
    np.random.seed(42)

    full = prepare_raw_equivalent(pd.read_parquet(test_path))
    if train_path:
        train_full = prepare_raw_equivalent(pd.read_parquet(train_path))
        train_df, val_df = train_test_split(train_full, test_size=0.15, random_state=42)
        test_df = full
    else:
        train_df, temp_df = train_test_split(full, test_size=0.30, random_state=42)
        val_df, test_df = train_test_split(temp_df, test_size=0.50, random_state=42)

    eu, cad, falt = tekla_paths or DEFAULT_TEKLA_PATHS
    profile_lookup = build_profile_lookup_from_tekla_csvs(eu, cad, falt)

    needed = set()
    for d in (train_df, val_df, test_df):
        needed |= set(d["BEAM"]) | set(d["COLUMN"])
    missing = check_profile_coverage(needed, profile_lookup)
    if missing:
        raise KeyError(f"Faltan {len(missing)} perfiles en el catálogo Tekla: {missing}")

    train_df, val_df, test_df = (add_geometry_targets(d) for d in (train_df, val_df, test_df))

    pre = Preprocessor().fit(train_df)
    train_ds, val_ds, test_ds = (ConnectionDataset(d, pre) for d in (train_df, val_df, test_df))
    train_loader = DataLoader(train_ds, batch_size=64, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=128, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=128, shuffle=False)

    device = _device()
    model = _build_model(pre, device)
    fit(model, train_loader, val_loader, ConnectionDesignLoss(), device, epochs=epochs, lr=lr, verbose=False)

    outputs = predict_loader(model, test_loader, device)
    full_design = outputs_to_design(outputs, pre, reconstruct_p=True)
    metrics = _compute_metrics(test_df, full_design)

    global_df = pd.concat([train_df, val_df, test_df], ignore_index=True)
    meta = _save_bundle(model, pre, global_df, metrics, epochs, lr, mode="initial")
    return meta


# ---------------------------------------------------------------------------
# Reentrenamiento con el dataset global acumulado
# ---------------------------------------------------------------------------

def retrain(epochs=80, lr=1e-3, test_size=0.2) -> dict:
    """
    Reentrena DESDE CERO usando model_store/global_dataset.parquet completo
    (dataset original + filas nuevas validadas por el usuario). Se hace un split
    train/val/test nuevo en cada reentreno; el modelo y el preprocesador se
    sobrescriben solo si el entrenamiento termina sin errores.
    """
    global_df = load_global_dataset()
    if global_df is None or len(global_df) == 0:
        raise RuntimeError("No hay dataset global todavía. Entrena primero el modelo inicial.")

    torch.manual_seed(42)
    np.random.seed(42)

    train_df, temp_df = train_test_split(global_df, test_size=test_size, random_state=42)
    val_df, test_df = train_test_split(temp_df, test_size=0.5, random_state=42)

    pre = Preprocessor().fit(train_df)
    train_ds, val_ds, test_ds = (ConnectionDataset(d, pre) for d in (train_df, val_df, test_df))
    train_loader = DataLoader(train_ds, batch_size=64, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=128, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=128, shuffle=False)

    device = _device()
    model = _build_model(pre, device)
    fit(model, train_loader, val_loader, ConnectionDesignLoss(), device, epochs=epochs, lr=lr, verbose=False)

    outputs = predict_loader(model, test_loader, device)
    full_design = outputs_to_design(outputs, pre, reconstruct_p=True)
    metrics = _compute_metrics(test_df, full_design)

    meta = _save_bundle(model, pre, global_df, metrics, epochs, lr, mode="retrain")
    return meta


# ---------------------------------------------------------------------------
# Inferencia (GUI de usuario)
# ---------------------------------------------------------------------------

def load_model_bundle():
    if not model_exists():
        return None
    with open(PREPROCESSOR_PATH, "rb") as f:
        pre = pickle.load(f)
    device = _device()
    model = _build_model(pre, device)
    model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
    model.eval()
    return model, pre, device


def predict_df(input_df: pd.DataFrame, tekla_paths=None):
    """
    input_df: columnas "pobres" tipo fictional.csv (UNICODE, BEAM, COLUMN,
    Capacity_Moment, Capacity_Shear, Capacity_Axial, grado_acero, clase_tornillo).
    Devuelve (result_df, feats_df):
      - result_df: identificadores + TODAS las predicciones, incluida la
        reconstrucción de p1..p12 (una fila por fila de entrada).
      - feats_df: features "ricas" (lookup de perfil + material) usadas, necesarias
        más tarde para poder guardar filas validadas en el dataset global.
    """
    bundle = load_model_bundle()
    if bundle is None:
        raise RuntimeError("No hay ningún modelo entrenado todavía.")
    model, pre, device = bundle

    eu, cad, falt = tekla_paths or DEFAULT_TEKLA_PATHS
    profile_lookup = build_profile_lookup_from_tekla_csvs(eu, cad, falt)
    missing = check_profile_coverage(set(input_df["BEAM"]) | set(input_df["COLUMN"]), profile_lookup)
    if missing:
        raise KeyError(f"Perfiles no cubiertos por el catálogo Tekla: {missing}")

    feats = build_training_features(input_df, profile_lookup).reset_index(drop=True)

    x_cat, x_num = pre.transform_features(feats)
    outputs = forward_numpy(model, x_cat, x_num, device)
    design = outputs_to_design(outputs, pre, reconstruct_p=True)
    design = design.drop(columns=["_bolt_nominal_mm"], errors="ignore")

    id_cols = [c for c in ID_COLUMNS if c in input_df.columns]
    result = pd.concat([input_df[id_cols].reset_index(drop=True), design], axis=1)
    return result, feats


# ---------------------------------------------------------------------------
# Validación de predicciones -> nuevas filas del dataset global
# ---------------------------------------------------------------------------

def build_dataset_rows(feats_df: pd.DataFrame, design_df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensambla filas listas para el dataset global a partir de las features "ricas"
    (lookup de perfil/material, mismas para todas las filas de una predicción) y de
    las predicciones ya decodificadas (design_df, incluye DrawingCode/Bolt/SlipCritical/
    g,e,d,Bp,Lp,tp/geometría con nombre/rigidizadores/p1..p12 reconstruidas).
    Si ya existe un dataset global, se reordena/recorta a sus columnas exactas
    (columnas del dataset ausentes en la predicción quedan en NaN).
    """
    design_df = design_df.drop(columns=["_bolt_nominal_mm"], errors="ignore").reset_index(drop=True)
    combined = pd.concat([feats_df.reset_index(drop=True), design_df], axis=1)
    combined = combined.loc[:, ~combined.columns.duplicated()]

    global_df = load_global_dataset()
    if global_df is not None:
        for c in global_df.columns:
            if c not in combined.columns:
                combined[c] = np.nan
        combined = combined[global_df.columns]
    return combined


def append_validated_rows(rows_df: pd.DataFrame) -> int:
    """Añade filas ya validadas por el usuario al dataset global y lo guarda en disco.
    NO reentrena automáticamente: eso se hace explícitamente desde la GUI de admin."""
    global_df = load_global_dataset()
    if global_df is None:
        raise RuntimeError("No hay dataset global todavía. Entrena primero el modelo inicial.")
    new_df = pd.concat([global_df, rows_df], ignore_index=True)
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    new_df.to_parquet(GLOBAL_DATASET_PATH, index=False)
    return len(new_df)
