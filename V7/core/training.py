import copy
import numpy as np
import torch
from .postprocess import decode_predictions, derive_dependent_columns, _sigmoid
from .config import N_Y

def _split_batch(batch, device):
    x_cat = batch["x_cat"].to(device)
    x_num = batch["x_num"].to(device)
    targets = {k: v.to(device) for k, v in batch.items() if k not in ("x_cat", "x_num")}
    return x_cat, x_num, targets

def teacher_forcing_schedule(epoch, epochs, start=1.0, end=0.15, warmup_frac=0.15):
    warmup = max(1, int(epochs * warmup_frac))
    if epoch <= warmup:
        return start
    progress = (epoch - warmup) / max(1, epochs - warmup)
    return start + (end - start) * progress

def run_epoch(model, loader, criterion, device, optimizer=None, scheduler=None,
              clip_norm=5.0, use_true_transitions=True,
              teacher_forcing_ratio=0.0, noise_std=0.0):
    train = optimizer is not None
    model.train(train)
    total, sums, batches = 0.0, {}, 0
    for batch in loader:
        x_cat, x_num, targets = _split_batch(batch, device)
        transitions = targets["p_transition_idx"] if use_true_transitions else None
        p_teacher = targets["masked_value"][:, :N_Y] if train else None
        p_mask = targets["masked_mask"][:, :N_Y]
        with torch.set_grad_enabled(train):
            preds = model(
                x_cat, x_num, p_transition_idx=transitions,
                p_teacher=p_teacher, p_mask=p_mask,
                teacher_forcing_ratio=teacher_forcing_ratio if train else 0.0,
                noise_std=noise_std if train else 0.0,
            )
            loss, parts = criterion(preds, targets)
            if train:
                optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), clip_norm)
                optimizer.step()
                if scheduler is not None:
                    scheduler.step()
        total += loss.item(); batches += 1
        for k, v in parts.items():
            sums[k] = sums.get(k, 0.0) + v
    return total/batches, {k: v/batches for k, v in sums.items()}

def fit(model, train_loader, val_loader, criterion, device, epochs=100, lr=2e-3,
        weight_decay=1e-4, log_every=5, checkpoint_path=None,
        tf_start=1.0, tf_end=0.15, noise_std=0.05,
        validate_with_true_transitions=True, verbose=True):
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=lr, total_steps=epochs*len(train_loader), pct_start=0.15)
    history = {"train_loss": [], "val_loss": [], "train_parts": [], "val_parts": [],
               "teacher_forcing_ratio": [], "best_epoch": 0, "best_val_loss": float("inf")}
    best_val, best_state = float("inf"), None
    for epoch in range(1, epochs+1):
        tf_ratio = teacher_forcing_schedule(epoch, epochs, tf_start, tf_end)
        tr_loss, tr_parts = run_epoch(
            model, train_loader, criterion, device, optimizer, scheduler,
            use_true_transitions=True, teacher_forcing_ratio=tf_ratio, noise_std=noise_std)
        va_loss, va_parts = run_epoch(
            model, val_loader, criterion, device, optimizer=None,
            use_true_transitions=validate_with_true_transitions,
            teacher_forcing_ratio=0.0, noise_std=0.0)
        history["train_loss"].append(tr_loss); history["val_loss"].append(va_loss)
        history["train_parts"].append(tr_parts); history["val_parts"].append(va_parts)
        history["teacher_forcing_ratio"].append(tf_ratio)
        is_best = va_loss < best_val
        if is_best:
            best_val = va_loss; best_state = copy.deepcopy(model.state_dict())
            history["best_epoch"] = epoch; history["best_val_loss"] = va_loss
            if checkpoint_path is not None:
                torch.save({"epoch": epoch, "val_loss": va_loss,
                            "model_state_dict": best_state,
                            "optimizer_state_dict": optimizer.state_dict()}, checkpoint_path)
        if verbose and (epoch == 1 or epoch % log_every == 0 or is_best):
            print(f"epoch {epoch:03d}/{epochs} | train={tr_loss:.4f} | val={va_loss:.4f} | "
                  f"TF={tf_ratio:.2f} | p={va_parts['p_value']:.3f} | "
                  f"cum={va_parts['p_cumulative']:.3f} | "
                  f"p<=10={100*va_parts['p_within_10']:.1f}%" + (" | MEJOR" if is_best else ""))
    model.load_state_dict(best_state)
    return history

@torch.no_grad()
def forward_numpy(model, x_cat, x_num, device, p_transition_idx=None):
    model.eval()
    outputs = model(
        torch.as_tensor(x_cat, dtype=torch.long, device=device),
        torch.as_tensor(x_num, dtype=torch.float32, device=device),
        p_transition_idx=None if p_transition_idx is None else torch.as_tensor(p_transition_idx, dtype=torch.long, device=device),
        teacher_forcing_ratio=0.0,
    )
    return {k: v.detach().cpu().numpy() for k, v in outputs.items()}

def predict_loader(model, loader, device, use_true_transitions=False):
    out = []
    for batch in loader:
        transitions = batch["p_transition_idx"] if use_true_transitions else None
        out.append(forward_numpy(model, batch["x_cat"], batch["x_num"], device, transitions))
    return {k: np.concatenate([x[k] for x in out], axis=0) for k in out[0]}

def outputs_to_design(outputs, pre):
    design = decode_predictions(
        pre.inverse_reg_always(outputs["reg_always"]),
        pre.inverse_masked(outputs["masked_value"]),
        _sigmoid(outputs["masked_presence_logit"]),
        outputs["bolt_logits"], outputs["n_alma_logits"], outputs["n_cantonera_logits"],
        outputs["standard_logits"], pre.standard_encoder.classes_,
        outputs["slip_critical_logit"],
    )
    return derive_dependent_columns(design)
