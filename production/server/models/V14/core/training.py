"""Entrenamiento del PINN y reentreno desde el servidor.

  - ConnectionDataset / run_epoch / fit: bucle del notebook (celda 6), con la seleccion de
    epoca sobre VALIDACION y con la metrica estatica (independiente de los multiplicadores ALM).
  - retrain(): flujo completo que `retrain.py` delega si el core del modelo activo lo expone.

El PINN no usa etiquetas: las filas validadas (datos_modelo.parquet) amplian la distribucion de
entradas (perfiles, cargas, materiales); el diseno lo guia la fisica de `losses.py`.
"""
import json
import os
import random
import re
import shutil
import traceback
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset

from . import adapter as A
from .config import BOLT_DIAMETERS, GEOMETRY_COLUMNS, INPUT_DIM
from .dataset import Preprocessor
from .losses import PhysicsInformedALMLoss, static_score
from .model import BoltedConnectionPINN

DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")
SEED, EPOCHS, BATCH, WD = 42, 100, 64, 1e-4
FEASIBLE_TOL = 0.05        # violacion media admitida en C1 (flexion) y C2 (cortante)
MIN_TEST = 50              # filas de test minimas para poder promover
MIN_ROWS = 100             # filas validas minimas para reentrenar


class ConnectionDataset(Dataset):
    def __init__(self, feats: pd.DataFrame, pre: Preprocessor):
        self.x = torch.as_tensor(pre.transform(feats), dtype=torch.float32)

    def __len__(self):
        return len(self.x)

    def __getitem__(self, i):
        return self.x[i]


def forward_decoded(model, x):
    """Forward + geometria decodificada DIFERENCIABLE (diametro blando, como en el notebook)."""
    preds = model(x)
    diam = torch.tensor(BOLT_DIAMETERS, device=x.device, dtype=x.dtype)
    d_soft = (torch.softmax(preds["bolt_diam_logits"], dim=-1) * diam).sum(-1)
    dec = model.decode_geometry(preds, x, d_soft)
    dec["d_eff"] = d_soft
    return preds, dec


def run_epoch(model, loader, loss_fn, device, optimizer=None, clip=1.0):
    train = optimizer is not None
    model.train(train)
    n = 0
    acc = {"loss": 0.0, "mass": 0.0, "eta_M": 0.0, "eta_V": 0.0}
    viol = np.zeros(loss_fn.num_constraints)
    with torch.enable_grad() if train else torch.no_grad():
        for x in loader:
            x = x.to(device)
            if train:
                optimizer.zero_grad()
            preds, dec = forward_decoded(model, x)
            loss, m = loss_fn(preds, dec, x)
            if train:
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=clip)
                optimizer.step()
            b = len(x)
            n += b
            for k in acc:
                acc[k] += m[k] * b
            viol += m["violations"] * b
    out = {k: v / max(n, 1) for k, v in acc.items()}
    out["violations"] = viol / max(n, 1)
    return out


def _feasible(parts) -> bool:
    return bool(np.all(parts["violations"][:2] < FEASIBLE_TOL))


def fit(model, train_loader, val_loader, loss_fn, device, epochs=EPOCHS, lr=1e-3,
        weight_decay=WD, log_every=10):
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs, eta_min=1e-6)
    best = {"score": float("inf"), "epoch": -1, "state": None}
    history = []
    for ep in range(1, epochs + 1):
        tr = run_epoch(model, train_loader, loss_fn, device, opt)
        loss_fn.update_multipliers(tr["violations"])
        va = run_epoch(model, val_loader, loss_fn, device)
        score = static_score(va["mass"], va["violations"])
        ok = _feasible(va)
        history.append({"epoch": ep, "loss": tr["loss"], "val_score": score, "val_mass": va["mass"],
                        "val_eta_M": va["eta_M"], "val_violations": va["violations"].tolist(),
                        "feasible": ok})
        if ok and score < best["score"]:
            best = {"score": score, "epoch": ep,
                    "state": {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}}
        if ep % log_every == 0 or ep == 1:
            print(f"[pinn] ep {ep}/{epochs} loss {tr['loss']:.1f} val_score {score:.1f} "
                  f"eta_M {va['eta_M']:.3f} C1 {va['violations'][0]:.4f} feasible={ok}", flush=True)
        sched.step()
    if best["state"] is not None:
        model.load_state_dict(best["state"])
    return {"best_epoch": best["epoch"], "best_score": best["score"],
            "feasible": best["state"] is not None, "history": history}


# ------------------------------------------------------------------------------------
# Reentreno desde el servidor (lo invoca retrain.py; ver instrucciones de integracion)
# ------------------------------------------------------------------------------------
def _clean_dataset(raw: pd.DataFrame) -> pd.DataFrame:
    need = ["UNICODE", "BEAM", "COLUMN", "ratio_moment", "ratio_shear", "ratio_axial",
            "grado_acero", "clase_tornillo"]
    df = raw.dropna(subset=need).drop_duplicates("UNICODE").copy()
    for c in ("ratio_moment", "ratio_shear", "ratio_axial"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["ratio_moment", "ratio_shear", "ratio_axial"])
    lut = A._profile_lookup().index
    key = lambda s: s.astype(str).str.strip().str.upper()
    df = df[key(df["BEAM"]).isin(lut) & key(df["COLUMN"]).isin(lut)
            & df["grado_acero"].astype(str).isin(A.ACERO_TABLE)
            & df["clase_tornillo"].astype(str).isin(A.TORNILLO_TABLE)]
    return df.reset_index(drop=True)


def retrain(rm, config, pdir, next_name, bucket):
    """Reentrena partiendo del modelo activo (`pdir`), evalua contra el en test y guarda
    una nueva version `<BASE>.<N>`. Si es mejor y factible, queda como activa."""
    random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
    raw = pd.read_parquet(rm.MASTER)
    n_raw = len(raw)

    df = _clean_dataset(raw)
    feats = A.preprocess(df)
    ok_geom = (feats[["BEAM_d_mm", "BEAM_b_mm", "BEAM_tf_mm", "BEAM_tw_mm",
                      "COLUMN_d_mm", "COLUMN_b_mm", "COLUMN_tf_mm", "COLUMN_tw_mm"]] > 0).all(axis=1)
    feats, df = feats[ok_geom].reset_index(drop=True), df[ok_geom.to_numpy()].reset_index(drop=True)
    if len(feats) < MIN_ROWS:
        raise ValueError(f"Solo {len(feats)} filas validas para reentrenar (minimo {MIN_ROWS})")

    bk = feats["UNICODE"].map(bucket)                         # <15 test, <30 val, resto train
    te, va, tr = feats[bk < 15], feats[(bk >= 15) & (bk < 30)], feats[bk >= 30]
    if len(va) == 0:
        va = tr
    print(f"[pinn] train {len(tr)} val {len(va)} test {len(te)}", flush=True)

    pre = Preprocessor()
    ck = torch.load(pdir / "weights.pt", map_location="cpu", weights_only=False)
    hp = ck["hyperparameters"]

    def build():
        return BoltedConnectionPINN(INPUT_DIM, hp["hidden_dim"], hp["num_res_blocks"],
                                    hp.get("dropout_rate", 0.1))

    model = build()
    model.load_state_dict(ck["model_state_dict"])            # arranque en caliente
    model.to(DEV)

    ld = lambda d, sh=False: DataLoader(ConnectionDataset(d, pre), batch_size=BATCH, shuffle=sh)
    loss_fn = PhysicsInformedALMLoss(device=DEV)
    hist = fit(model, ld(tr, True), ld(va), loss_fn, DEV, epochs=EPOCHS, lr=hp.get("lr", 1e-3))

    ev = PhysicsInformedALMLoss(device=DEV)                   # solo mide masa + violaciones
    new_parts = run_epoch(model.eval(), ld(te if len(te) else va), ev, DEV)
    new_score = static_score(new_parts["mass"], new_parts["violations"])
    try:
        parent = build()
        parent.load_state_dict(ck["model_state_dict"])
        old_parts = run_epoch(parent.to(DEV).eval(), ld(te if len(te) else va), ev, DEV)
        old_score = static_score(old_parts["mass"], old_parts["violations"])
    except Exception:
        traceback.print_exc()
        old_score = None
    promoted = bool(old_score is not None and len(te) >= MIN_TEST and hist["feasible"]
                    and _feasible(new_parts) and new_score <= old_score)
    print(f"[pinn] score nuevo {new_score:.2f} | padre {old_score} | promoted {promoted}", flush=True)

    base = config.MODEL_NAME.split(".")[0]
    name = next_name(base)
    tmp = config.MODELS_DIR / f"_building_{name}"
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(pdir / "core", tmp / "core", ignore=shutil.ignore_patterns("__pycache__"))
    ad = tmp / "core" / "adapter.py"
    ad.write_text(re.sub(r"^MODEL_NAME = .*$", "MODEL_NAME = Path(__file__).resolve().parent.parent.name",
                         ad.read_text(encoding="utf-8"), flags=re.M), encoding="utf-8")
    (tmp / "data").mkdir()
    for f in (pdir / "data").glob("tekla_*.csv"):
        shutil.copy(f, tmp / "data" / f.name)
    raw.to_parquet(tmp / "data" / "datos_modelo.parquet", index=False)
    torch.save({"model_state_dict": {k: v.cpu() for k, v in model.state_dict().items()},
                "hyperparameters": hp, "epoch": hist["best_epoch"]}, tmp / "weights.pt")
    joblib.dump(pre, tmp / "preprocessor.joblib")
    meta = {"name": name, "parent": config.MODEL_NAME, "date": datetime.now().isoformat(timespec="seconds"),
            "rows_used": len(feats), "rows_raw": n_raw, "train": len(tr), "val": len(va), "test": len(te),
            "score_new": new_score, "score_parent": old_score, "promoted": promoted,
            "best_epoch": hist["best_epoch"], "feasible": hist["feasible"],
            "eta_M_test": new_parts["eta_M"], "mass_test": new_parts["mass"],
            "violations_test": new_parts["violations"].tolist()}
    (tmp / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    os.replace(tmp, config.MODELS_DIR / name)
    if promoted:
        (config.MODELS_DIR / "active.json").write_text(json.dumps({"name": name}), encoding="utf-8")
    rm.update(status="done", new_version=name, promoted=promoted, activated=False,
              rows_at_last_train=n_raw, pid=None, last_error=None)