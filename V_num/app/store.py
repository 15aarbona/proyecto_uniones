"""
Capa de orquestación entre las GUIs (tkinter) y el pipeline (core/).

Responsabilidades:
  - Guardar / cargar el "bundle" del modelo: pesos (model.pt), preprocesador
    ajustado (preprocessor.pkl) y metadatos (metadata.json).
  - Guardar / cargar el DATASET GLOBAL (model_store/global_dataset.parquet):
    el dataframe YA preparado para entrenar, con la ESTRUCTURA NUEVA (v4, esquema de
    data/train_v3.parquet): p1..p12 con máscara, n_alma, n_cantonera, standard, Bolt int,
    Lh, y las features derivadas del input (lookup Tekla + resistencias). Se reconstruye
    con rebuild_global_dataset() a partir de los parquet "ricos" (train_v2/test_v2, que
    traen Capacity_* y los conteos) y REEMPLAZA al dataset global antiguo.
  - train_initial(): primer entrenamiento a partir de parquet rico; crea el dataset
    global = train+val+test ya convertido a la estructura nueva.
  - retrain(): reentrena DESDE CERO usando el dataset global acumulado (que puede
    incluir filas nuevas validadas por el usuario).
  - predict_df(): inferencia sobre un CSV "pobre" tipo fictional.csv.
  - build_dataset_rows() / append_validated_rows(): una vez el usuario valida
    predicciones, se ensamblan como filas con el mismo esquema del dataset global
    y se añaden (se guardan, no se reentrena automáticamente).
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
    infer_source_from_profile,
)
from core.dataset import Preprocessor, ConnectionDataset, counts_from_ys, ys_from_p
from core.config import P_COLUMNS, Y_COLUMNS
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

# Estructura canónica del dataset global: esquema "rico" persistido en PASOS p1..p12
# (no en Ys: las Ys se derivan en post-proceso) + conteos de
# estructura n_alma/n_cantonera. Lh se añade al final porque es un target del esquema
# train_v3 que no existe en el parquet v2 (se inyecta del v3 hermano).
GLOBAL_SCHEMA = (
    ["Capacity_Moment", "Capacity_Shear", "Capacity_Axial",
     "g", "tws", "Bp", "Lp", "tp", "e", "d"]
    + P_COLUMNS
    + ["ts", "tbs", "tst",
       "Hole", "BEAM", "COLUMN", "DrawingCode", "Bolt", "SlipCritical",
       "grado_acero", "clase_tornillo", "Source", "standard",
       "BEAM_type", "BEAM_d_mm", "BEAM_bf_mm", "BEAM_tw_mm", "BEAM_tf_mm", "BEAM_r1_mm", "BEAM_wely_mm", "BEAM_w_kgm",
       "COLUMN_type", "COLUMN_d_mm", "COLUMN_bf_mm", "COLUMN_tw_mm", "COLUMN_tf_mm", "COLUMN_r1_mm", "COLUMN_wely_mm", "COLUMN_w_kgm",
       "fy_acero_mpa", "fu_acero_mpa", "fy_tornillo_mpa", "fu_tornillo_mpa", "fv_tornillo_mpa",
       "n_cantonera", "n_alma", "Lh"]
)


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


# ---------------------------------------------------------------------------
# Conversión del esquema "rico" (train_v2/test_v2) a la estructura nueva (v4)
# ---------------------------------------------------------------------------

def _inject_lh_if_needed(df: pd.DataFrame, source_path) -> pd.DataFrame:
    """
    Los parquet ricos tipo train_v2.parquet NO traen Lh (se quedó fuera), pero sí la trae
    su hermano train_v3.parquet, alineado fila a fila con v2 (verificado). Si falta Lh,
    se busca el parquet v3 equivalente junto al dado y se inyecta con aserciones de
    alineación; si no se puede, error claro.
    """
    if "Lh" in df.columns:
        return df
    p = Path(source_path)
    v3_path = p.with_name(p.name.replace("v2", "v3"))
    if not v3_path.exists():
        raise KeyError(
            f"'{p.name}' no trae 'Lh' (necesaria en la estructura nueva) y no se encontró "
            f"'{v3_path.name}' para tomarla. Usa el parquet v3 equivalente o uno que incluya Lh."
        )
    v3 = pd.read_parquet(v3_path)
    if len(v3) != len(df):
        raise KeyError(f"{v3_path.name} no tiene las mismas filas que {p.name}: no se puede inyectar Lh de forma segura.")
    check_cols = [c for c in ("g", "e", "d", "Bp", "tp", "Bolt", "standard") if c in df.columns and c in v3.columns]
    if check_cols and not (df[check_cols].reset_index(drop=True) == v3[check_cols].reset_index(drop=True)).all().all():
        raise KeyError(f"{v3_path.name} no está alineado fila a fila con {p.name}: no se inyecta Lh.")
    df = df.copy()
    df["Lh"] = v3["Lh"].values
    return df


def build_global_structure(df: pd.DataFrame, source_path=None) -> pd.DataFrame:
    """
    Parquet rico (tipo data/train_v2.parquet: Capacity_*, BEAM/COLUMN, tipos, fy/fu,
    p1..p12, Lp, Hole, DrawingCode, Source, standard, Bolt int) -> dataframe con la
    estructura GLOBAL_SCHEMA exacta (pasos p1..p12 + n_alma/n_cantonera). Si falta Lh se
    inyecta del parquet v3 hermano (source_path). Si faltan n_alma/n_cantonera se derivan
    de las Ys (p -> Y). Lh negativo (basura del dataset crudo) se limpia a 0.
    """
    if source_path is not None:
        df = _inject_lh_if_needed(df, source_path)
    df = df.copy()

    renames = {"AceroEstructural": "grado_acero", "EstandarTornillos": "clase_tornillo"}
    df = df.rename(columns={k: v for k, v in renames.items() if k in df.columns})

    missing = [c for c in GLOBAL_SCHEMA
               if c not in df.columns and c not in ("n_alma", "n_cantonera", "Lh")]
    if missing:
        raise KeyError(f"Faltan columnas en el parquet de entrada: {missing}")

    if "n_alma" not in df.columns or "n_cantonera" not in df.columns:
        n_alma, n_cantonera, _ = counts_from_ys(ys_from_p(df))
        df["n_alma"] = n_alma
        df["n_cantonera"] = n_cantonera

    # Lh: en el crudo hay sentinelas negativos (int32 min) -> 0 = sin cartabón
    df["Lh"] = df["Lh"].clip(lower=0.0)

    # coherencia: las Ys derivadas de p deben ser un prefijo y cuadrar con los conteos
    Y = ys_from_p(df)[Y_COLUMNS].values
    active = (Y > 0).astype(int)
    assert ((active[:, :-1] == 0) & (active[:, 1:] == 1)).sum() == 0, \
        "Las Ys derivadas de p deben formar un prefijo Y1..Y_k"
    assert (active.sum(axis=1) == df["n_alma"].values + df["n_cantonera"].values + 1).all(), \
        "nº de Ys activas != n_alma + n_cantonera + 1"

    df["Bolt"] = df["Bolt"].astype(int)
    df["n_alma"] = df["n_alma"].astype(int)
    df["n_cantonera"] = df["n_cantonera"].astype(int)

    return df[GLOBAL_SCHEMA].reset_index(drop=True)


def rebuild_global_dataset(rich_paths: list[Path]) -> pd.DataFrame:
    """
    Lee los parquet ricos (p.ej. data/train_v2.parquet + data/test_v2.parquet, con sus
    hermanos v3 al lado para Lh), los convierte a la estructura nueva y SOBRESCRIBE
    model_store/global_dataset.parquet.
    """
    parts = [build_global_structure(pd.read_parquet(p), source_path=p) for p in rich_paths]
    global_df = pd.concat(parts, ignore_index=True)
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    global_df.to_parquet(GLOBAL_DATASET_PATH, index=False)
    return global_df


def _build_model(pre: Preprocessor, device) -> ConnectionDesignNet:
    return ConnectionDesignNet(
        cat_cardinalities=pre.cat_cardinalities,
        num_continuous=len(pre.num_scaler.mean_),
        n_standard_classes=pre.n_standard_classes,
    ).to(device)


def _build_criterion(pre: Preprocessor) -> ConnectionDesignLoss:
    return ConnectionDesignLoss(
        n_alma_weights=pre.count_class_weights["n_alma"],
        n_cantonera_weights=pre.count_class_weights["n_cantonera"],
    )


def _compute_metrics(test_df: pd.DataFrame, full_design: pd.DataFrame) -> dict:
    def _acc(col, cast=None):
        real = test_df[col].reset_index(drop=True)
        pred = full_design[col].reset_index(drop=True)
        if cast:
            real, pred = cast(real), cast(pred)
        return float((real.values == pred.values).mean())

    cls_acc = {
        "standard": _acc("standard", lambda s: s.astype(str)),
        "Bolt": _acc("Bolt", lambda s: s.astype(int)),
        "SlipCritical": _acc("SlipCritical", lambda s: s.astype(str).str.upper()
                             .map({"TRUE": "YES", "FALSE": "NO", "YES": "YES", "NO": "NO"})),
        "n_alma": _acc("n_alma", lambda s: s.astype(int)),
        "n_cantonera": _acc("n_cantonera", lambda s: s.astype(int)),
    }

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
        "n_standard_classes": pre.n_standard_classes,
        "standard_classes": list(pre.standard_encoder.classes_),
        "count_class_weights": {k: v.tolist() for k, v in pre.count_class_weights.items()},
        "metrics": metrics,
    }
    METADATA_PATH.write_text(json.dumps(meta, indent=2, default=str))

    hist = load_history()
    hist.append(meta)
    HISTORY_PATH.write_text(json.dumps(hist, indent=2, default=str))
    return meta


# ---------------------------------------------------------------------------
# Entrenamiento
# ---------------------------------------------------------------------------

def _train_from_df(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame,
                   epochs: int, lr: float, mode: str) -> dict:
    """
    train_df/val_df/test_df vienen en el esquema persistido (p1..p12). El modelo se
    entrena sobre las p1..p12 directamente (son target del modelo); el dataset global
    que se guarda es el de pasos p.
    """
    torch.manual_seed(42)
    np.random.seed(42)

    # (las Y ya no se derivan ni son target: las p son el target directo del modelo)

    pre = Preprocessor().fit(train_df)
    train_ds, val_ds, test_ds = (ConnectionDataset(d, pre) for d in (train_df, val_df, test_df))
    train_loader = DataLoader(train_ds, batch_size=64, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=128, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=128, shuffle=False)

    device = _device()
    model = _build_model(pre, device)
    criterion = _build_criterion(pre).to(device)
    fit(model, train_loader, val_loader, criterion, device,
        epochs=epochs, lr=lr, verbose=False)

    outputs = predict_loader(model, test_loader, device)
    full_design = outputs_to_design(outputs, pre)
    metrics = _compute_metrics(test_df, full_design)

    global_df = pd.concat([train_df, val_df, test_df], ignore_index=True)[GLOBAL_SCHEMA]
    meta = _save_bundle(model, pre, global_df, metrics, epochs, lr, mode=mode)
    return meta


def train_initial(test_path, train_path=None, epochs=150, lr=2e-3, tekla_paths=None) -> dict:
    """
    Primer entrenamiento. Los parquet de entrada son "ricos" (data/train_v2.parquet /
    data/test_v2.parquet o equivalentes: con Capacity_*, Y1..Y12, n_alma/n_cantonera,
    standard, Bolt int; si no traen Lh se inyecta del v3 hermano). Se convierten a la
    estructura nueva y AL terminar se guarda el bundle del modelo Y el dataset global
    (train+val+test ya en la estructura nueva), que reemplaza al global_dataset.parquet
    anterior.
    Si no se pasa train_path, hace split interno de test_path (modo smoke test).
    """
    full = build_global_structure(pd.read_parquet(test_path), source_path=test_path)
    if train_path is not None:
        train_full = build_global_structure(pd.read_parquet(train_path), source_path=train_path)
        train_df, val_df = train_test_split(train_full, test_size=0.15, random_state=42)
        test_df = full
    else:
        train_df, temp_df = train_test_split(full, test_size=0.30, random_state=42)
        val_df, test_df = train_test_split(temp_df, test_size=0.50, random_state=42)

    return _train_from_df(train_df, val_df, test_df, epochs, lr, mode="initial")


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

    missing = [c for c in GLOBAL_SCHEMA if c not in global_df.columns]
    if missing:
        raise KeyError(f"El dataset global no tiene la estructura esperada. Faltan: {missing}")

    torch.manual_seed(42)
    np.random.seed(42)

    train_df, temp_df = train_test_split(global_df, test_size=test_size, random_state=42)
    val_df, test_df = train_test_split(temp_df, test_size=0.5, random_state=42)

    # (las Y ya no se derivan ni son target: las p son el target directo del modelo)

    pre = Preprocessor().fit(train_df)
    train_ds, val_ds, test_ds = (ConnectionDataset(d, pre) for d in (train_df, val_df, test_df))
    train_loader = DataLoader(train_ds, batch_size=64, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=128, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=128, shuffle=False)

    device = _device()
    model = _build_model(pre, device)
    criterion = _build_criterion(pre).to(device)
    fit(model, train_loader, val_loader, criterion, device,
        epochs=epochs, lr=lr, verbose=False)

    outputs = predict_loader(model, test_loader, device)
    full_design = outputs_to_design(outputs, pre)
    metrics = _compute_metrics(test_df, full_design)

    meta = _save_bundle(model, pre, global_df[GLOBAL_SCHEMA], metrics, epochs, lr, mode="retrain")
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
      - result_df: identificadores + TODAS las predicciones (Ys acumuladas, conteos
        n_alma/n_cantonera, chapa, rigidizadores, p1..p12 reconstruidas).
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
    design = outputs_to_design(outputs, pre)
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
    las predicciones ya decodificadas (design_df, con Ys, n_alma/n_cantonera, chapa,
    rigidizadores y p1..p12 reconstruidas). Se recorta al esquema GLOBAL_SCHEMA.
    Columnas que el modelo ya no predice se rellenan de forma derivada:
      - Source = European/Canadian según el prefijo del perfil BEAM
      - Lp     = 2e + p (relación geométrica estándar; no es target)
      - DrawingCode = NaN (metadato, ya no se modela: la head es 'standard')
    """
    feats = feats_df.reset_index(drop=True)
    design_df = design_df.drop(columns=["_bolt_nominal_mm"], errors="ignore").reset_index(drop=True)

    combined = pd.concat([feats, design_df], axis=1)
    combined = combined.loc[:, ~combined.columns.duplicated()]

    if "BEAM" in combined.columns:
        if "Source" not in combined.columns:
            combined["Source"] = combined["BEAM"].map(infer_source_from_profile)
        if "DrawingCode" not in combined.columns:
            combined["DrawingCode"] = np.nan
    if "Lp" not in combined.columns or combined["Lp"].isna().all():
        Sp = combined[[c for c in P_COLUMNS if c in combined.columns]].fillna(0.0).sum(axis=1)
        combined["Lp"] = 2 * combined["e"] + Sp
    if "Hole" not in combined.columns:
        combined["Hole"] = combined["_bolt_nominal_mm"].astype(int) + 2 if "_bolt_nominal_mm" in combined else \
            combined["Bolt"].astype(int) + 2

    combined["SlipCritical"] = combined["SlipCritical"].astype(str).str.upper()\
                             .map({"TRUE": 1, "FALSE": 0, "YES": 1, "NO": 0}).astype(bool)

    schema = global_df.columns if (global_df := load_global_dataset()) is not None else GLOBAL_SCHEMA
    for c in schema:
        if c not in combined.columns:
            combined[c] = np.nan
    return combined[list(schema)]


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
