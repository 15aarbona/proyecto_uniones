"""Persistencia, entrenamiento e inferencia de la aplicación V3."""
import json
import pickle
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader

from core.config import CATEGORICAL_FEATURES, NUMERIC_FEATURES, ID_COLUMNS
from core.dataset import Preprocessor, ConnectionDataset
from core.evaluation import evaluate
from core.lookups import build_profile_lookup_from_tekla_csvs, check_profile_coverage, build_training_features
from core.losses import ConnectionDesignLoss
from core.model import ConnectionDesignNet
from core.postprocess import decode
from core.training import fit, predict

APP_DIR = Path(__file__).parent
STORE_DIR = APP_DIR / "model_store"
DATA_DIR = APP_DIR / "data"
MODEL_PATH = STORE_DIR / "model.pt"
PREPROCESSOR_PATH = STORE_DIR / "preprocessor.pkl"
METADATA_PATH = STORE_DIR / "metadata.json"
GLOBAL_DATASET_PATH = STORE_DIR / "global_dataset.parquet"
HISTORY_PATH = STORE_DIR / "training_history.json"
DEFAULT_TEKLA_PATHS = (DATA_DIR / "tekla_eu.csv", DATA_DIR / "tekla_cad.csv", DATA_DIR / "tekla_faltante.csv")


def model_exists():
    return MODEL_PATH.exists() and PREPROCESSOR_PATH.exists() and METADATA_PATH.exists()


def load_metadata():
    return json.loads(METADATA_PATH.read_text(encoding="utf-8")) if METADATA_PATH.exists() else None


def load_history():
    return json.loads(HISTORY_PATH.read_text(encoding="utf-8")) if HISTORY_PATH.exists() else []


def load_global_dataset():
    return pd.read_parquet(GLOBAL_DATASET_PATH) if GLOBAL_DATASET_PATH.exists() else None


def _device():
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _read_table(path):
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls", ".xlsm"):
        return pd.read_excel(path)
    if path.suffix.lower() in (".parquet", ".pq"):
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _normalise(df):
    df = df.copy()
    df.columns = df.columns.str.strip()
    for c in [f"p{i}_label" for i in range(1, 13)]:
        df[c] = df[c].fillna("UNUSED").astype(str).str.strip()
        p = c.replace("_label", "")
        df.loc[df[c].eq("UNUSED"), p] = 0
    return df


def _safe_stratify(df):
    counts = df["DrawingCode"].value_counts()
    return df["DrawingCode"] if len(counts) > 1 and counts.min() >= 2 else None


def _split(full, external_test=None):
    if external_test is not None:
        train, val = train_test_split(full, test_size=.15, random_state=42, stratify=_safe_stratify(full))
        return train.reset_index(drop=True), val.reset_index(drop=True), external_test.reset_index(drop=True)
    train_val, test = train_test_split(full, test_size=.20, random_state=42, stratify=_safe_stratify(full))
    train, val = train_test_split(train_val, test_size=.1875, random_state=42, stratify=_safe_stratify(train_val))
    return *(x.reset_index(drop=True) for x in (train, val, test)),


def _build_model(pre, device):
    return ConnectionDesignNet(pre.cat_cardinalities, len(NUMERIC_FEATURES), pre.n_drawing_codes, pre.n_p_labels).to(device)


def _loaders(train_df, val_df, test_df, pre):
    datasets = [ConnectionDataset(x, pre) for x in (train_df, val_df, test_df)]
    return (DataLoader(datasets[0], batch_size=64, shuffle=True, drop_last=len(datasets[0]) >= 64),
            DataLoader(datasets[1], batch_size=256), DataLoader(datasets[2], batch_size=256))


def _metrics(test_df, design):
    cls, labels, regression, structure = evaluate(test_df, design)
    return {"n_test": len(test_df), "classification_accuracy": cls,
            "p_label_accuracy": labels.to_dict(), "structure": structure,
            "regression_table": regression.to_dict(orient="records")}


def _save_bundle(model, pre, global_df, metrics, epochs, lr, mode):
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), MODEL_PATH)
    with PREPROCESSOR_PATH.open("wb") as f:
        pickle.dump(pre, f)
    global_df.to_parquet(GLOBAL_DATASET_PATH, index=False)
    meta = {"version": "V3-p-labels", "trained_at": datetime.now().isoformat(timespec="seconds"),
            "mode": mode, "epochs": epochs, "lr": lr, "n_rows_dataset": len(global_df),
            "n_drawing_codes": pre.n_drawing_codes, "drawing_code_classes": list(pre.drawing_encoder.classes_),
            "p_label_classes": list(pre.p_label_encoder.classes_), "metrics": metrics}
    METADATA_PATH.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    history = load_history(); history.append(meta)
    HISTORY_PATH.write_text(json.dumps(history, indent=2, default=str), encoding="utf-8")
    return meta


def _train(train_df, val_df, test_df, epochs, lr):
    pre = Preprocessor().fit(train_df)
    loaders = _loaders(train_df, val_df, test_df, pre)
    device = _device(); model = _build_model(pre, device)
    fit(model, loaders[0], loaders[1], ConnectionDesignLoss(), device, epochs=epochs, lr=lr)
    design = decode(predict(model, loaders[2], device), pre)
    return model, pre, _metrics(test_df, design)


def train_initial(test_path, train_path=None, epochs=150, lr=2e-3, tekla_paths=None):
    """Entrena desde un CSV/Excel rico. Si se aporta train_path, test_path queda como test externo."""
    torch.manual_seed(42); np.random.seed(42)
    if train_path:
        train_full, external_test = _normalise(_read_table(train_path)), _normalise(_read_table(test_path))
        train_df, val_df, test_df = _split(train_full, external_test)
        global_df = pd.concat([train_full, external_test], ignore_index=True)
    else:
        full = _normalise(_read_table(test_path))
        train_df, val_df, test_df = _split(full)
        global_df = full
    model, pre, metrics = _train(train_df, val_df, test_df, epochs, lr)
    return _save_bundle(model, pre, global_df, metrics, epochs, lr, "initial")


def retrain(epochs=80, lr=1e-3, test_size=.20):
    full = load_global_dataset()
    if full is None or full.empty:
        raise RuntimeError("No hay dataset global. Entrena primero el modelo inicial.")
    torch.manual_seed(42); np.random.seed(42)
    train_df, val_df, test_df = _split(_normalise(full))
    model, pre, metrics = _train(train_df, val_df, test_df, epochs, lr)
    return _save_bundle(model, pre, full, metrics, epochs, lr, "retrain")


def load_model_bundle():
    if not model_exists(): return None
    with PREPROCESSOR_PATH.open("rb") as f: pre = pickle.load(f)
    device = _device(); model = _build_model(pre, device)
    model.load_state_dict(torch.load(MODEL_PATH, map_location=device)); model.eval()
    return model, pre, device


def predict_df(input_df, tekla_paths=None):
    bundle = load_model_bundle()
    if bundle is None: raise RuntimeError("No hay ningún modelo V3 entrenado todavía.")
    model, pre, device = bundle
    eu, cad, falt = tekla_paths or DEFAULT_TEKLA_PATHS
    lookup = build_profile_lookup_from_tekla_csvs(eu, cad, falt)
    missing = check_profile_coverage(set(input_df["BEAM"]) | set(input_df["COLUMN"]), lookup)
    if missing: raise KeyError(f"Perfiles no cubiertos por el catálogo Tekla: {missing}")
    feats = build_training_features(input_df, lookup).reset_index(drop=True)
    xcat, xnum = pre.transform_features(feats)
    with torch.no_grad():
        raw = model(torch.as_tensor(xcat).to(device), torch.as_tensor(xnum, dtype=torch.float32).to(device))
    design = decode({k: v.cpu().numpy() for k, v in raw.items()}, pre)
    ids = [c for c in ID_COLUMNS if c in input_df]
    if "UNICODE" in input_df: ids.insert(0, "UNICODE")
    return pd.concat([input_df[ids].reset_index(drop=True), design], axis=1), feats


def build_dataset_rows(feats_df, design_df):
    combined = pd.concat([feats_df.reset_index(drop=True), design_df.reset_index(drop=True)], axis=1)
    combined = combined.loc[:, ~combined.columns.duplicated()]
    global_df = load_global_dataset()
    if global_df is not None:
        for c in global_df.columns:
            if c not in combined: combined[c] = np.nan
        combined = combined[global_df.columns]
    return combined


def append_validated_rows(rows_df):
    global_df = load_global_dataset()
    if global_df is None: raise RuntimeError("No hay dataset global.")
    result = pd.concat([global_df, rows_df], ignore_index=True)
    result.to_parquet(GLOBAL_DATASET_PATH, index=False)
    return len(result)