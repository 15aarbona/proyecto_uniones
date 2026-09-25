"""
Bucle de entrenamiento / predicción compartido por train.py y pipeline_walkthrough.ipynb
(así no hay lógica duplicada entre ambos).
"""
import copy

import numpy as np
import torch

from .postprocess import decode_predictions, derive_dependent_columns, _sigmoid


def _split_batch(batch, device):
    x_cat = batch["x_cat"].to(device)
    x_num = batch["x_num"].to(device)
    targets = {k: v.to(device) for k, v in batch.items() if k not in ("x_cat", "x_num")}
    return x_cat, x_num, targets


def run_epoch(model, loader, criterion, device, optimizer=None, scheduler=None, clip_norm=5.0):
    """Una época. Con optimizer -> entrena; sin optimizer -> evalúa. Devuelve (loss, partes)."""
    train = optimizer is not None
    model.train(train)
    total, parts_sum = 0.0, {}
    for batch in loader:
        x_cat, x_num, targets = _split_batch(batch, device)
        with torch.set_grad_enabled(train):
            preds = model(x_cat, x_num)
            loss, parts = criterion(preds, targets)
            if train:
                optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), clip_norm)
                optimizer.step()
                if scheduler is not None:
                    scheduler.step()
        total += loss.item()
        for k, v in parts.items():
            parts_sum[k] = parts_sum.get(k, 0.0) + v
    n = len(loader)
    return total / n, {k: v / n for k, v in parts_sum.items()}


def fit(model, train_loader, val_loader, criterion, device, epochs=80, lr=2e-3,
        weight_decay=1e-4, log_every=None, verbose=True):
    """
    AdamW + OneCycle (por batch). Se conserva y restaura el checkpoint con menor val_loss.
    Devuelve history = {train_loss, val_loss, train_parts, val_parts, best_epoch}.
    """
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=lr, total_steps=epochs * len(train_loader), pct_start=0.15)

    history = {"train_loss": [], "val_loss": [], "train_parts": [], "val_parts": [], "best_epoch": 0}
    best_val, best_state = float("inf"), None
    log_every = log_every or max(1, epochs // 10)

    for epoch in range(1, epochs + 1):
        tr_loss, tr_parts = run_epoch(model, train_loader, criterion, device, optimizer, scheduler)
        va_loss, va_parts = run_epoch(model, val_loader, criterion, device)
        history["train_loss"].append(tr_loss)
        history["val_loss"].append(va_loss)
        history["train_parts"].append(tr_parts)
        history["val_parts"].append(va_parts)
        if va_loss < best_val:
            best_val, best_state = va_loss, copy.deepcopy(model.state_dict())
            history["best_epoch"] = epoch
        if verbose and (epoch % log_every == 0 or epoch == 1):
            print(f"epoch {epoch:03d}/{epochs} | train={tr_loss:.4f} | val={va_loss:.4f} | "
                  f"val masked_value={va_parts['masked_value']:.3f} presence={va_parts['masked_presence']:.3f}")

    if best_state is not None:
        model.load_state_dict(best_state)
    if verbose:
        print(f"mejor val_loss={best_val:.4f} en la época {history['best_epoch']} (pesos restaurados)")
    return history


@torch.no_grad()
def forward_numpy(model, x_cat, x_num, device):
    """Forward en modo eval sobre arrays/tensores; devuelve dict de arrays numpy."""
    model.eval()
    preds = model(torch.as_tensor(x_cat).to(device),
                  torch.as_tensor(x_num, dtype=torch.float32).to(device))
    return {k: v.cpu().numpy() for k, v in preds.items()}


def predict_loader(model, loader, device):
    outs = [forward_numpy(model, b["x_cat"], b["x_num"], device) for b in loader]
    return {k: np.concatenate([o[k] for o in outs], axis=0) for k in outs[0]}


def outputs_to_design(outputs, pre, reconstruct_p=False):
    """Salidas crudas de la red (dict numpy) -> diseño completo con columnas derivadas."""
    design = decode_predictions(
        reg_always_real=pre.inverse_reg_always(outputs["reg_always"]),
        masked_value_real=pre.inverse_masked(outputs["masked_value"]),
        masked_presence_prob=_sigmoid(outputs["masked_presence_logit"]),
        bolt_logits=outputs["bolt_logits"],
        drawing_code_logits=outputs["drawing_code_logits"],
        drawing_code_classes=pre.drawing_code_encoder.classes_,
        slip_critical_logit=outputs["slip_critical_logit"],
    )
    return derive_dependent_columns(design, reconstruct_p=reconstruct_p)
