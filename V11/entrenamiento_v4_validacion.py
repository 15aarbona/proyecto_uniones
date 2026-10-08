# Generated from: entrenamiento_v4_validacion.ipynb
# Converted at: 2026-10-08T07:32:36.234Z
# Next step (optional): refactor into modules & generate tests with RunCell
# Quick start: pip install runcell

# # Entrenamiento y validación v4: p discretizadas + topología conjunta
# 
# Este notebook entrena el modelo, lo valida con **topología real** (techo de la parte de p) y con **inferencia realista** (topología predicha), y muestra todas las métricas relevantes para las separaciones `p1…p12`.
# 
# **Antes de ejecutar**
# 
# 1. Sustituye en `core/` los archivos `model.py`, `losses.py`, `training.py` y `evaluation.py` por los nuevos. `config.py`, `dataset.py` y `postprocess.py` **no cambian**.
# 2. Copia también `core/diagnostico_p.py` (opcional, para los diagnósticos).
# 3. Ajusta `DATA_PATH` y, si quieres, el diccionario `CFG` de la sección 1.
# 
# **Qué se compara.** `CFG["model"] = "v3"` reproduce tu modelo anterior (regresión de p). `"v4"` usa la cabeza discretizada de 5 mm. La sección 18 ejecuta una ablación escalonada (A→E) con varias semillas, que es lo que de verdad dice qué cambio ayuda. El test tiene 480 filas, así que diferencias de ±1,5 puntos son ruido.


%load_ext autoreload
%autoreload 2

from pathlib import Path
import copy
import random
import time
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import torch
from torch.utils.data import DataLoader
from sklearn.model_selection import GroupShuffleSplit, train_test_split

from core.config import *
from core.dataset import (
    Preprocessor,
    ConnectionDataset,
    validate_connection_targets,
    validate_transition_labels,
)
from core.model import ConnectionDesignNet, ConnectionDesignNetV4, n_bins_from_train, p_confidence
from core.losses import ConnectionDesignLoss, ConnectionDesignLossV4
from core.training import fit, predict_loader
from core.evaluation import (
    preparar_para_evaluar,
    evaluar_predicciones,
    evaluar_estructura,
    evaluar_sesgo_p,
    evaluar_acumulado_y,
    evaluar_por_transicion,
    resumen_p,
    contribucion_error_topologia,
    calibracion_confianza_p,
)

pd.set_option("display.max_columns", 200)
pd.set_option("display.width", 220)

# ## 1. Configuración
# 
# `CFG` define el experimento principal:
# 
# | clave | valores | efecto |
# |---|---|---|
# | `model` | `"v3"` / `"v4"` | v3 = regresión de p (tu modelo anterior); v4 = p discretizada en bins de 5 mm |
# | `joint_topology` | `True` / `False` | solo v4: una softmax conjunta sobre (n_alma, n_cantonera) |
# | `class_weights` | `True` / `False` | pesos inversos a la frecuencia en los conteos. `False` optimiza la exactitud directamente |
# | `select_metric` | `"val_loss"`, `"p_and_topology"`, `"p_within_10"`, `"p_mae_mm"`, `"topology_exact"` | criterio para elegir la mejor época (en validación realista). `p_and_topology` = % de p dentro de ±10 mm + % de topología exacta; evita elegir épocas tempranas con buena p pero mala topología |
# | `w_p_ce`, `label_scale_bins` | números | peso de la cross-entropy de p y suavizado ordinal de la etiqueta (solo v4) |


SEED = 42
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

DATA_PATH = Path("data/global_dataset.parquet")
OUTPUT_DIR = Path("artifacts_v4")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
BEST_CHECKPOINT = OUTPUT_DIR / "best_v4.pt"

BATCH_SIZE = 128
EPOCHS = 200
LEARNING_RATE = 2e-3
WEIGHT_DECAY = 1e-4
NUM_WORKERS = 0

HIDDEN_DIM = 192
NUM_BLOCKS = 3
DROPOUT = 0.10
GRU_HIDDEN_DIM = 128

DEFAULT_CFG = dict(
    model="v4",
    joint_topology=True,
    class_weights=False,
    select_metric="p_and_topology",
    w_p_ce=2.0,
    label_scale_bins=1.0,
)
CFG = {**DEFAULT_CFG}          # <- edita aqui el experimento principal

RUN_DIAGNOSTICS = True         # cierre geometrico, multimodalidad, duplicados
USE_DERIVED_FEATURES = False   # ratios M/d (experimental)
RUN_ABLATION = True           # seccion 18 (tarda: 5 configuraciones x semillas)
ABLATION_SEEDS = [0, 1, 2]


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


set_seed(SEED)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False
print("Dispositivo:", DEVICE)
print("Experimento :", CFG)

# ## 2. Carga y validación del dataset


suffix = DATA_PATH.suffix.lower()
if suffix == ".parquet":
    df = pd.read_parquet(DATA_PATH)
elif suffix == ".csv":
    df = pd.read_csv(DATA_PATH)
elif suffix in {".xlsx", ".xls"}:
    df = pd.read_excel(DATA_PATH)
else:
    raise ValueError(f"Formato no soportado: {suffix}")

df = df.reset_index(drop=True)
print("Dimensiones:", df.shape)

required_columns = (
    CATEGORICAL_FEATURES + NUMERIC_FEATURES + REGRESSION_ALWAYS + MASKED_COLUMNS
    + ["standard", "Bolt", "SlipCritical", "n_alma", "n_cantonera"]
)
missing = [c for c in required_columns if c not in df.columns]
if missing:
    raise ValueError(f"Faltan columnas obligatorias: {missing}")

numeric_columns = list(dict.fromkeys(
    NUMERIC_FEATURES + REGRESSION_ALWAYS + MASKED_COLUMNS + ["n_alma", "n_cantonera"]
))
for c in numeric_columns:
    df[c] = pd.to_numeric(df[c], errors="coerce")

df[MASKED_COLUMNS] = df[MASKED_COLUMNS].fillna(0.0)
essential = CATEGORICAL_FEATURES + NUMERIC_FEATURES + REGRESSION_ALWAYS + [
    "standard", "Bolt", "SlipCritical", "n_alma", "n_cantonera"
]
before = len(df)
df = df.dropna(subset=essential).reset_index(drop=True)
print(f"Filas eliminadas por nulos: {before - len(df)}")

bolt_numeric = df["Bolt"].astype(str).str.replace("M", "", regex=False).astype(int)
unknown_bolts = sorted(set(bolt_numeric) - set(CATALOGO_BOLT))
if unknown_bolts:
    raise ValueError(f"Bolt fuera de catalogo: {unknown_bolts}")

cv = validate_connection_targets(df)
print("Conexiones con prefijo y conteo coherentes:", cv["valid"].mean())
if not cv["valid"].all():
    df = df.loc[cv["valid"].to_numpy()].reset_index(drop=True)

lv = validate_transition_labels(df)
if lv is not None:
    print("Etiquetas de transicion coherentes:", lv.mean())
    if not lv.all():
        raise ValueError("Hay etiquetas de transicion incompatibles con la topologia.")
else:
    print("No hay columnas pX_transition: se derivan de n_alma y n_cantonera.")

# La cabeza v4 asume que las p estan en una rejilla de Y_GRID_STEP mm.
vals = df[P_COLUMNS].to_numpy(float)
act = vals > 0
on_grid = np.mean(np.isclose(vals[act] % Y_GRID_STEP, 0) | np.isclose(vals[act] % Y_GRID_STEP, Y_GRID_STEP))
print(f"p activas en rejilla de {Y_GRID_STEP} mm: {100 * on_grid:.1f}%  (si es < ~98% revisa la rejilla)")
print("Filas finales:", len(df))

# ## 3. Características derivadas (opcional)
# 
# Si activas `USE_DERIVED_FEATURES`, se añaden ratios de demanda frente al canto. Para añadir **propiedades de perfil** (`tf`, `tw`, `bf`, `Wpl` de viga y columna) haz lo mismo: une la tabla de perfiles a `df` creando las columnas y añádelas a `NUMERIC_FEATURES` **antes** de crear el `Preprocessor`.
# 
# ```python
# df = df.merge(tabla_perfiles_viga, on=["BEAM_type", "BEAM_d_mm"], how="left")
# NUMERIC_FEATURES.extend(["BEAM_tf_mm", "BEAM_tw_mm", "BEAM_bf_mm"])
# ```


if USE_DERIVED_FEATURES:
    df["M_over_beam_d"] = df["Capacity_Moment"] / df["BEAM_d_mm"]
    df["M_over_col_d"] = df["Capacity_Moment"] / df["COLUMN_d_mm"]
    df["V_over_beam_d"] = df["Capacity_Shear"] / df["BEAM_d_mm"]
    for c in ["M_over_beam_d", "M_over_col_d", "V_over_beam_d"]:
        df[c] = df[c].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        if c not in NUMERIC_FEATURES:
            NUMERIC_FEATURES.append(c)   # modifica la lista compartida con core.dataset
print("Numericas de entrada:", len(NUMERIC_FEATURES), NUMERIC_FEATURES)

# ## 4. División entrenamiento / validación / prueba (por `Unicode`)


GROUP_COLUMN = "Unicode" if "Unicode" in df.columns else None

if GROUP_COLUMN is not None:
    split_test = GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=SEED)
    tv_idx, test_idx = next(split_test.split(df, groups=df[GROUP_COLUMN]))
    df_train_val = df.iloc[tv_idx].reset_index(drop=True)
    df_test = df.iloc[test_idx].reset_index(drop=True)
    split_val = GroupShuffleSplit(n_splits=1, test_size=0.1765, random_state=SEED)
    tr_idx, va_idx = next(split_val.split(df_train_val, groups=df_train_val[GROUP_COLUMN]))
    df_train = df_train_val.iloc[tr_idx].reset_index(drop=True)
    df_val = df_train_val.iloc[va_idx].reset_index(drop=True)
    assert set(df_train[GROUP_COLUMN]).isdisjoint(set(df_val[GROUP_COLUMN]))
    assert set(df_train[GROUP_COLUMN]).isdisjoint(set(df_test[GROUP_COLUMN]))
else:
    df_train_val, df_test = train_test_split(df, test_size=0.15, random_state=SEED)
    df_train, df_val = train_test_split(df_train_val, test_size=0.1765, random_state=SEED)
    df_train, df_val, df_test = [d.reset_index(drop=True) for d in (df_train, df_val, df_test)]

print("Train:", len(df_train), "| Val:", len(df_val), "| Test:", len(df_test))

for name, other in [("validacion", df_val), ("test", df_test)]:
    unk = {c: sorted(set(other[c].astype(str)) - set(df_train[c].astype(str))) for c in CATEGORICAL_FEATURES}
    unk = {c: v for c, v in unk.items() if v}
    print(f"Categorias desconocidas en {name}:", unk)
    if unk:
        raise ValueError("LabelEncoder no admite categorias desconocidas.")

# ## 5. Diagnósticos previos (sobre entrenamiento)
# 
# - **Cierre geométrico**: si `e + Σp + d` es casi función exacta de `BEAM_d_mm` (residuo de pocos mm), existe una restricción que el modelo no conoce y conviene parametrizar las p como fracciones de ese total.
# - **Multimodalidad**: si `top3_pct` es alto, las p son casi categóricas y la regresión a la media es mala idea.
# - **Duplicados de entrada**: mide el suelo de ruido irreducible.


if RUN_DIAGNOSTICS:
    try:
        from core.diagnostico_p import cierre_geometrico, multimodalidad, duplicados_entrada
        print("CIERRE GEOMETRICO (filas 'todas' primero)")
        cg = cierre_geometrico(df_train)
        display(cg[cg.grupo == "todas"])
        print("MULTIMODALIDAD POR TRANSICION")
        display(multimodalidad(df_train))
        print("SUELO DE RUIDO (entradas identicas)")
        display(duplicados_entrada(df_train))
    except ImportError:
        print("core/diagnostico_p.py no encontrado: se omiten los diagnosticos.")

# ## 6. Preprocesador, datasets y loaders


pre = Preprocessor().fit(df_train)
train_dataset = ConnectionDataset(df_train, pre)
val_dataset = ConnectionDataset(df_val, pre)
test_dataset = ConnectionDataset(df_test, pre)

loader_kw = dict(batch_size=BATCH_SIZE, num_workers=NUM_WORKERS, pin_memory=torch.cuda.is_available())
train_loader = DataLoader(train_dataset, shuffle=True, **loader_kw)
val_loader = DataLoader(val_dataset, shuffle=False, **loader_kw)
test_loader = DataLoader(test_dataset, shuffle=False, **loader_kw)

N_BINS = n_bins_from_train(df_train, P_COLUMNS, step_mm=Y_GRID_STEP)
print(f"Bins de p: {N_BINS} (hasta {(N_BINS - 1) * Y_GRID_STEP} mm, paso {Y_GRID_STEP} mm)")

# ## 7. Construcción del modelo, decodificación y utilidades


def build_experiment(cfg):
    model_kw = dict(
        cat_cardinalities=pre.cat_cardinalities,
        num_continuous=len(NUMERIC_FEATURES),
        n_standard_classes=pre.n_standard_classes,
        p_mean_mm=pre.masked_mean[:N_Y],
        p_std_mm=pre.masked_std[:N_Y],
        hidden_dim=HIDDEN_DIM,
        num_blocks=NUM_BLOCKS,
        dropout=DROPOUT,
        gru_hidden_dim=GRU_HIDDEN_DIM,
        previous_p_scale_mm=200.0,
        cumulative_scale_mm=1000.0,
    )
    w_alma = pre.count_class_weights["n_alma"] if cfg["class_weights"] else np.ones(N_ALMA_CLASSES, np.float32)
    w_cant = pre.count_class_weights["n_cantonera"] if cfg["class_weights"] else np.ones(N_CANTONERA_CLASSES, np.float32)
    loss_kw = dict(
        n_alma_weights=w_alma,
        n_cantonera_weights=w_cant,
        presence_pos_weight=pre.presence_pos_weight,
        p_mean_mm=pre.masked_mean[:N_Y],
        p_std_mm=pre.masked_std[:N_Y],
        w_cls=1.0, w_counts=1.0, w_reg=1.0,
        w_p_value=2.0, w_p_cumulative=0.1,
        w_stiffener_value=1.0, w_masked_presence=0.5,
        cumulative_scale_mm=20.0, p_tolerance_mm=10.0,
    )
    if cfg["model"] == "v3":
        model = ConnectionDesignNet(**model_kw)
        criterion = ConnectionDesignLoss(**loss_kw)
    elif cfg["model"] == "v4":
        model = ConnectionDesignNetV4(**model_kw, n_p_bins=N_BINS, p_bin_step_mm=Y_GRID_STEP,
                                      joint_topology=cfg["joint_topology"])
        criterion = ConnectionDesignLossV4(**loss_kw, n_p_bins=N_BINS, p_bin_step_mm=Y_GRID_STEP,
                                           joint_topology=cfg["joint_topology"],
                                           w_p_ce=cfg["w_p_ce"], label_scale_bins=cfg["label_scale_bins"])
    else:
        raise ValueError(cfg["model"])
    return model.to(DEVICE), criterion.to(DEVICE)


CATALOGS = {"g": CATALOGO_g, "e": CATALOGO_e, "d": CATALOGO_d, "Bp": CATALOGO_Bp, "tp": CATALOGO_tp,
            "tws": CATALOGO_tws, "ts": CATALOGO_ts, "tbs": CATALOGO_tbs, "tst": CATALOGO_tst}


def sigmoid_np(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


def snap_to_catalog(values, catalog):
    values = np.asarray(values, dtype=float)
    if catalog is None:
        return values
    catalog = np.asarray(catalog, dtype=float)
    return catalog[np.abs(values[:, None] - catalog[None, :]).argmin(axis=1)]


def decode_outputs(outputs, preprocessor):
    reg = preprocessor.inverse_reg_always(outputs["reg_always"])
    masked = preprocessor.inverse_masked(outputs["masked_value"])
    presence = sigmoid_np(outputs["masked_presence_logit"])
    n_alma = outputs["n_alma_logits"].argmax(axis=1)
    n_cantonera = outputs["n_cantonera_logits"].argmax(axis=1)
    k = n_alma + n_cantonera + 1

    result = {}
    for j, name in enumerate(REGRESSION_ALWAYS):
        result[name] = snap_to_catalog(reg[:, j], CATALOGS[name])

    p = np.maximum(np.round(masked[:, :N_Y] / Y_GRID_STEP) * Y_GRID_STEP, Y_GRID_STEP)
    active = np.arange(N_Y)[None, :] < k[:, None]
    p = np.where(active, p, 0.0)
    for j, name in enumerate(P_COLUMNS):
        result[name] = p[:, j]

    for j, name in enumerate(STIFFENER_COLUMNS):
        values = snap_to_catalog(masked[:, N_Y + j], CATALOGS[name])
        result[name] = np.where(presence[:, N_Y + j] >= 0.5, values, 0.0)

    result["Bolt"] = np.asarray(CATALOGO_BOLT)[outputs["bolt_logits"].argmax(axis=1)]
    result["standard"] = preprocessor.standard_encoder.classes_[outputs["standard_logits"].argmax(axis=1)]
    result["SlipCritical"] = np.where(sigmoid_np(outputs["slip_critical_logit"]) >= 0.5, "YES", "NO")
    result["n_alma"] = n_alma
    result["n_cantonera"] = n_cantonera
    result["Hole"] = result["Bolt"] + 2
    result["num_filas_tornillos"] = n_alma + n_cantonera + 2
    result["tiene_cantonera"] = n_cantonera > 0
    return pd.DataFrame(result)


def predict_designs(model, loader):
    out_true = predict_loader(model, loader, DEVICE, use_true_transitions=True)
    out_real = predict_loader(model, loader, DEVICE, use_true_transitions=False)
    return out_true, out_real, decode_outputs(out_true, pre), decode_outputs(out_real, pre)


def kpis(design_real, design_true):
    r = resumen_p(df_test, design_real)
    t = resumen_p(df_test, design_true)
    ok = ((df_test["n_alma"].astype(int).to_numpy() == design_real["n_alma"].astype(int).to_numpy())
          & (df_test["n_cantonera"].astype(int).to_numpy() == design_real["n_cantonera"].astype(int).to_numpy()))
    return {
        "p_MAE_mm": r["MAE_mm"],
        "p_pct_10mm": r["pct_<=10mm"],
        "p_pct_>20mm": r["pct_>20mm"],
        "p99_mm": r["p99_abs_mm"],
        "topologia_exacta_%": 100 * ok.mean(),
        "p_pct_10mm_topologia_real": t["pct_<=10mm"],
    }

# ## 8. Prueba de una pasada antes de entrenar


set_seed(SEED)
model, criterion = build_experiment(CFG)
print(f"Parametros entrenables: {sum(p.numel() for p in model.parameters() if p.requires_grad):,}")

sample = next(iter(train_loader))
x_cat = sample["x_cat"].to(DEVICE)
x_num = sample["x_num"].to(DEVICE)
targets = {k: v.to(DEVICE) for k, v in sample.items() if k not in {"x_cat", "x_num"}}
with torch.no_grad():
    out = model(
        x_cat, x_num,
        p_transition_idx=targets["p_transition_idx"],
        p_teacher=targets["masked_value"][:, :N_Y],
        active_count=targets["n_alma_idx"] + targets["n_cantonera_idx"] + 1,
        teacher_forcing_ratio=1.0,
    )
    loss0, parts0 = criterion(out, targets)
print("Loss inicial:", float(loss0))
for k, v in out.items():
    print(f"{k:28s}", tuple(v.shape))

# ## 9. Entrenamiento
# 
# La mejor época se elige con `CFG["select_metric"]` sobre **validación realista** (topología predicha, sin teacher forcing).


set_seed(SEED)
model, criterion = build_experiment(CFG)
t0 = time.time()
history = fit(
    model=model,
    train_loader=train_loader,
    val_loader=val_loader,
    criterion=criterion,
    device=DEVICE,
    epochs=EPOCHS,
    lr=LEARNING_RATE,
    weight_decay=WEIGHT_DECAY,
    checkpoint_path=BEST_CHECKPOINT,
    log_every=10,
    tf_start=1.0,
    tf_end=0.15,
    tf_warmup_fraction=0.15,
    select_metric=CFG["select_metric"],
)
print(f"Tiempo de entrenamiento: {(time.time() - t0) / 60:.1f} min")

# ## 10. Curvas de entrenamiento


def curve(key, scale=1.0):
    return [scale * x.get(key, np.nan) for x in history["val_parts"]]

fig, ax = plt.subplots(2, 2, figsize=(15, 9))
ax[0, 0].plot(history["train_loss"], label="Train (TF + topologia real)")
ax[0, 0].plot(history["val_loss"], label="Val realista")
ax[0, 0].set_title("Perdida total"); ax[0, 0].legend()
ax[0, 1].plot(curve("p_within_10", 100), color="tab:orange")
ax[0, 1].set_title("p dentro de ±10 mm (val realista, %)")
ax[1, 0].plot(curve("p_mae_mm"), color="tab:green")
ax[1, 0].set_title("MAE de p (val realista, mm)")
ax[1, 1].plot(curve("topology_exact", 100), color="tab:red")
ax[1, 1].set_title("Topologia exacta (val, %) - solo v4")
for a in ax.ravel():
    a.axvline(history["best_epoch"] - 1, color="black", linestyle="--", alpha=0.6)
    a.set_xlabel("Epoca"); a.grid(True)
plt.tight_layout(); plt.show()
print("Mejor epoca:", history["best_epoch"], "| criterio:", history["select_metric"])

# ## 11. Predicción en test: topología real y realista


out_true, out_real, design_true, design_real = predict_designs(model, test_loader)
display(design_real.head())

# ## 12. Métricas de p
# 
# Tres lecturas:
# 
# - **topología real** = lo que da la parte de p cuando la estructura está bien (techo);
# - **inferencia realista** = lo que verá el usuario final;
# - **colas** (`pct_>20mm`, `p95`, `p99`): ahí está el problema de fiabilidad.


summary = pd.DataFrame({
    "topologia real": resumen_p(df_test, design_true),
    "inferencia realista": resumen_p(df_test, design_real),
})
display(summary.round(2))

print("=== TOPOLOGIA REAL ===")
real_df, pred_df = preparar_para_evaluar(df_test, design_true)
metrics_true = evaluar_predicciones(real_df, pred_df)

print("\n=== INFERENCIA REALISTA ===")
real_df, pred_df = preparar_para_evaluar(df_test, design_real)
metrics_realistic = evaluar_predicciones(real_df, pred_df)

# ## 13. Topología: exactitud, confusión y contribución al error de p


print("Exactitud de estructura:")
structure = evaluar_estructura(df_test, design_real)

real_na = df_test["n_alma"].astype(int).reset_index(drop=True)
real_nc = df_test["n_cantonera"].astype(int).reset_index(drop=True)
print("\nConfusion n_alma")
display(pd.crosstab(real_na.rename("real"), design_real["n_alma"].astype(int).rename("pred")))
print("Confusion n_cantonera")
display(pd.crosstab(real_nc.rename("real"), design_real["n_cantonera"].astype(int).rename("pred")))

print("Contribucion de la topologia al error de p")
topology_contribution = contribucion_error_topologia(df_test, design_real)
display(topology_contribution.round(2))

# ## 14. Sesgo, posición acumulada y transiciones


bias_table = evaluar_sesgo_p(df_test, design_real)
print("Sesgo por p (inferencia realista)")
display(bias_table.round(2))

position_table = evaluar_acumulado_y(df_test, design_real, incluir_e=True)
print("Error de posicion acumulada absoluta (incluye e)")
display(position_table.round(2))

transition_summary, transition_detail = evaluar_por_transicion(df_test, design_real)
print("Por transicion (peores primero)")
display(transition_summary.round(2))

real_matrix = df_test[P_COLUMNS].fillna(0.0).to_numpy(float)
pred_matrix_r = design_real[P_COLUMNS].to_numpy(float)
pred_matrix_t = design_true[P_COLUMNS].to_numpy(float)
active_m = real_matrix > 0

err_r = np.abs(pred_matrix_r - real_matrix)[active_m]
err_t = np.abs(pred_matrix_t - real_matrix)[active_m]

fig, ax = plt.subplots(1, 2, figsize=(15, 4.5))
bins = np.arange(0, 105, 5)
ax[0].hist(np.clip(err_r, 0, 100), bins=bins, alpha=0.6, label="realista")
ax[0].hist(np.clip(err_t, 0, 100), bins=bins, alpha=0.6, label="topologia real")
ax[0].set_yscale("log"); ax[0].set_xlabel("|error| p (mm, recortado a 100)"); ax[0].set_title("Distribucion del error (cola pesada)")
ax[0].legend(); ax[0].grid(True)

pct_r = [100 * np.mean(np.abs(pred_matrix_r[active_m[:, j], j] - real_matrix[active_m[:, j], j]) <= 10) if active_m[:, j].any() else np.nan for j in range(N_Y)]
pct_t = [100 * np.mean(np.abs(pred_matrix_t[active_m[:, j], j] - real_matrix[active_m[:, j], j]) <= 10) if active_m[:, j].any() else np.nan for j in range(N_Y)]
x = np.arange(N_Y)
ax[1].bar(x - 0.2, pct_r, 0.4, label="realista")
ax[1].bar(x + 0.2, pct_t, 0.4, label="topologia real")
ax[1].set_xticks(x); ax[1].set_xticklabels(P_COLUMNS); ax[1].set_ylim(60, 101)
ax[1].set_title("% de p dentro de ±10 mm por posicion"); ax[1].legend(); ax[1].grid(True)
plt.tight_layout(); plt.show()

# ## 15. Casos extremos


abs_err = np.abs(pred_matrix_r - real_matrix)
abs_err[~active_m] = np.nan
extreme = pd.DataFrame({
    "indice_test": np.arange(len(df_test)),
    "max_error_mm": np.nanmax(abs_err, axis=1),
    "mean_error_mm": np.nanmean(abs_err, axis=1),
    "peor_p": np.nanargmax(abs_err, axis=1) + 1,
    "n_alma_real": df_test["n_alma"].astype(int).to_numpy(),
    "n_alma_pred": design_real["n_alma"].astype(int).to_numpy(),
    "n_cantonera_real": df_test["n_cantonera"].astype(int).to_numpy(),
    "n_cantonera_pred": design_real["n_cantonera"].astype(int).to_numpy(),
})
extreme["topologia_correcta"] = (
    (extreme.n_alma_real == extreme.n_alma_pred) & (extreme.n_cantonera_real == extreme.n_cantonera_pred)
)
extreme = extreme.sort_values("max_error_mm", ascending=False)
display(extreme.head(25).round(2))
print("Entre las 40 peores conexiones, con topologia incorrecta:", int((~extreme.head(40).topologia_correcta).sum()))

# ## 16. Confianza de las p (solo v4) y triaje
# 
# La cabeza discreta devuelve una distribución por separación. `prob_dentro_10` es la masa de probabilidad a ≤ ±10 mm de la moda. Si está bien calibrada, sirve para **marcar conexiones que un ingeniero debería revisar**.


if CFG["model"] == "v4":
    p_mode_prob, p_prob10 = p_confidence(out_real["p_logits"])
    print("Calibracion (tramo de confianza predicha vs acierto real <=10 mm)")
    display(calibracion_confianza_p(df_test, design_real, p_prob10).round(2))

    k_pred = design_real["n_alma"].astype(int).to_numpy() + design_real["n_cantonera"].astype(int).to_numpy() + 1
    active_pred = np.arange(N_Y)[None, :] < k_pred[:, None]
    conn_conf = np.where(active_pred, p_prob10, 1.0).min(axis=1)

    topo_ok = ((df_test["n_alma"].astype(int).to_numpy() == design_real["n_alma"].astype(int).to_numpy())
               & (df_test["n_cantonera"].astype(int).to_numpy() == design_real["n_cantonera"].astype(int).to_numpy()))
    all_p_ok = np.all((np.abs(pred_matrix_r - real_matrix) <= 10) | ~active_m, axis=1) & topo_ok

    rows = []
    for thr in [0.5, 0.7, 0.85, 0.95]:
        flagged = conn_conf < thr
        rows.append({
            "umbral_confianza": thr,
            "% conexiones marcadas para revision": 100 * flagged.mean(),
            "% correctas entre las NO marcadas": 100 * all_p_ok[~flagged].mean() if (~flagged).any() else np.nan,
            "% correctas global": 100 * all_p_ok.mean(),
        })
    print("Triaje: conexion correcta = topologia correcta y todas las p dentro de ±10 mm")
    display(pd.DataFrame(rows).round(1))
else:
    print("Modelo v3: no hay distribucion por p, se omite la confianza.")

# ## 17. Guardado de artefactos


FINAL_MODEL_PATH = OUTPUT_DIR / "model_final.pt"
torch.save(
    {
        "model_state_dict": model.state_dict(),
        "cfg": CFG,
        "best_epoch": history["best_epoch"],
        "n_p_bins": N_BINS,
        "p_bin_step_mm": Y_GRID_STEP,
        "cat_cardinalities": pre.cat_cardinalities,
        "numeric_features": list(NUMERIC_FEATURES),
        "n_standard_classes": pre.n_standard_classes,
        "hidden_dim": HIDDEN_DIM, "num_blocks": NUM_BLOCKS, "dropout": DROPOUT, "gru_hidden_dim": GRU_HIDDEN_DIM,
        "p_mean_mm": pre.masked_mean[:N_Y], "p_std_mm": pre.masked_std[:N_Y],
    },
    FINAL_MODEL_PATH,
)
joblib.dump(pre, OUTPUT_DIR / "preprocessor.joblib")
joblib.dump(history, OUTPUT_DIR / "history.joblib")
design_real.to_parquet(OUTPUT_DIR / "test_predictions.parquet", index=False)

with pd.ExcelWriter(OUTPUT_DIR / "metricas.xlsx", engine="openpyxl") as writer:
    summary.to_excel(writer, sheet_name="resumen_p")
    metrics_true.to_excel(writer, sheet_name="topologia_real", index=False)
    metrics_realistic.to_excel(writer, sheet_name="inferencia_realista", index=False)
    topology_contribution.to_excel(writer, sheet_name="contribucion_topologia", index=False)
    bias_table.to_excel(writer, sheet_name="sesgo_p", index=False)
    position_table.to_excel(writer, sheet_name="posicion_acumulada", index=False)
    transition_summary.to_excel(writer, sheet_name="transiciones", index=False)
    extreme.to_excel(writer, sheet_name="casos_extremos", index=False)
print("Artefactos en:", OUTPUT_DIR.resolve())

# ## 18. Ablación escalonada con varias semillas (opcional)
# 
# Cada paso cambia **una cosa** respecto al anterior:
# 
# | | modelo | pesos de clase | topología | selección de época |
# |---|---|---|---|---|
# | A | v3 original | sí | independiente | `val_loss` |
# | B | v3 | **no** | independiente | `val_loss` |
# | C | **v4 (p discreta)** | no | independiente | `val_loss` |
# | D | v4 | no | **conjunta** | `val_loss` |
# | E | v4 | no | conjunta | **`p_and_topology`** |
# 
# Activa `RUN_ABLATION = True` en la sección 1. Con 3 semillas son 15 entrenamientos: en CPU puede tardar bastante, así que reduce `EPOCHS` si solo quieres una comparación rápida. Las semillas cambian la inicialización y el orden de los lotes, no la partición de datos.


# ABLATION_CONFIGS = {
#     "A_v3_original": {**DEFAULT_CFG, "model": "v3", "joint_topology": False, "class_weights": True, "select_metric": "val_loss"},
#     "B_v3_sin_pesos": {**DEFAULT_CFG, "model": "v3", "joint_topology": False, "class_weights": False, "select_metric": "val_loss"},
#     "C_v4_p_discreta": {**DEFAULT_CFG, "model": "v4", "joint_topology": False, "class_weights": False, "select_metric": "val_loss"},
#     "D_v4_topologia_conjunta": {**DEFAULT_CFG, "model": "v4", "joint_topology": True, "class_weights": False, "select_metric": "val_loss"},
#     "E_v4_seleccion_por_p": {**DEFAULT_CFG, "model": "v4", "joint_topology": True, "class_weights": False, "select_metric": "p_and_topology"},
# }

# ablation_rows = []
# if RUN_ABLATION:
#     for name, cfg in ABLATION_CONFIGS.items():
#         for seed in ABLATION_SEEDS:
#             set_seed(seed)
#             m, crit = build_experiment(cfg)
#             fit(m, train_loader, val_loader, crit, DEVICE, epochs=EPOCHS, lr=LEARNING_RATE,
#                 weight_decay=WEIGHT_DECAY, checkpoint_path=None, log_every=10**9,
#                 select_metric=cfg["select_metric"], verbose=False)
#             _, _, d_true, d_real = predict_designs(m, test_loader)
#             ablation_rows.append({"config": name, "seed": seed, **kpis(d_real, d_true)})
#             print(f"{name} seed={seed}: p<=10mm {ablation_rows[-1]['p_pct_10mm']:.1f}% | "
#                   f"topologia {ablation_rows[-1]['topologia_exacta_%']:.1f}%")
#     ablation = pd.DataFrame(ablation_rows)
#     agg = ablation.groupby("config").agg(["mean", "std"]).drop(columns="seed")
#     display(agg.round(2))
#     ablation.to_csv(OUTPUT_DIR / "ablacion.csv", index=False)
# else:
#     print("RUN_ABLATION=False: omitida.")