"""
Bucle de entrenamiento, validación e inferencia.
"""

import copy

import numpy as np
import torch

from .postprocess import (
    decode_predictions,
    derive_dependent_columns,
    _sigmoid,
)


def _split_batch(
    batch,
    device,
):
    x_cat = batch["x_cat"].to(device)
    x_num = batch["x_num"].to(device)

    targets = {
        key: value.to(device)
        for key, value in batch.items()
        if key not in (
            "x_cat",
            "x_num",
        )
    }

    return x_cat, x_num, targets


def run_epoch(
    model,
    loader,
    criterion,
    device,
    optimizer=None,
    scheduler=None,
    clip_norm=5.0,
    use_true_transitions=None,
):
    """
    Ejecuta una época.

    Parameters
    ----------
    optimizer:
        Si no es None, se entrena el modelo.

    use_true_transitions:
        True:
            utiliza las transiciones derivadas de los conteos reales.

        False:
            el modelo utiliza las transiciones derivadas de sus
            conteos predichos.

        None:
            True durante entrenamiento y False durante validación.
    """
    train = optimizer is not None

    if use_true_transitions is None:
        use_true_transitions = train

    model.train(train)

    total_loss = 0.0
    parts_sum = {}
    n_batches = 0

    for batch in loader:
        x_cat, x_num, targets = (
            _split_batch(
                batch=batch,
                device=device,
            )
        )

        transition_input = (
            targets["p_transition_idx"]
            if use_true_transitions
            else None
        )

        with torch.set_grad_enabled(train):
            predictions = model(
                x_cat=x_cat,
                x_num=x_num,
                p_transition_idx=(
                    transition_input
                ),
            )

            loss, parts = criterion(
                predictions,
                targets,
            )

            if train:
                optimizer.zero_grad()

                loss.backward()

                torch.nn.utils.clip_grad_norm_(
                    model.parameters(),
                    clip_norm,
                )

                optimizer.step()

                if scheduler is not None:
                    scheduler.step()

        total_loss += loss.item()

        for key, value in parts.items():
            parts_sum[key] = (
                parts_sum.get(key, 0.0)
                + value
            )

        n_batches += 1

    if n_batches == 0:
        raise RuntimeError(
            "El DataLoader no contiene batches."
        )

    mean_loss = (
        total_loss
        / n_batches
    )

    mean_parts = {
        key: value / n_batches
        for key, value
        in parts_sum.items()
    }

    return mean_loss, mean_parts


def fit(
    model,
    train_loader,
    val_loader,
    criterion,
    device,
    epochs=80,
    lr=2e-3,
    weight_decay=1e-4,
    log_every=None,
    verbose=True,
    checkpoint_path=None,
):
    """
    Entrena el modelo y conserva la época con menor pérdida de
    validación.

    La validación utiliza transiciones derivadas de los conteos
    predichos, reproduciendo el comportamiento de producción.

    Al finalizar, model contiene los mejores pesos.
    """
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=lr,
        weight_decay=weight_decay,
    )

    scheduler = (
        torch.optim.lr_scheduler.OneCycleLR(
            optimizer,
            max_lr=lr,
            total_steps=(
                epochs
                * len(train_loader)
            ),
            pct_start=0.15,
        )
    )

    history = {
        "train_loss": [],
        "val_loss": [],
        "train_parts": [],
        "val_parts": [],
        "best_epoch": 0,
        "best_val_loss": float("inf"),
    }

    best_val = float("inf")
    best_state = None

    if log_every is None:
        log_every = max(
            1,
            epochs // 10,
        )

    for epoch in range(
        1,
        epochs + 1,
    ):
        train_loss, train_parts = (
            run_epoch(
                model=model,
                loader=train_loader,
                criterion=criterion,
                device=device,
                optimizer=optimizer,
                scheduler=scheduler,
                use_true_transitions=True,
            )
        )

        val_loss, val_parts = (
            run_epoch(
                model=model,
                loader=val_loader,
                criterion=criterion,
                device=device,
                optimizer=None,
                scheduler=None,
                use_true_transitions=False,
            )
        )

        history["train_loss"].append(
            train_loss
        )

        history["val_loss"].append(
            val_loss
        )

        history["train_parts"].append(
            train_parts
        )

        history["val_parts"].append(
            val_parts
        )

        is_best = val_loss < best_val

        if is_best:
            best_val = val_loss

            best_state = copy.deepcopy(
                model.state_dict()
            )

            history["best_epoch"] = epoch
            history["best_val_loss"] = (
                val_loss
            )

            if checkpoint_path is not None:
                torch.save(
                    {
                        "epoch": epoch,
                        "val_loss": val_loss,
                        "model_state_dict": (
                            best_state
                        ),
                        "optimizer_state_dict": (
                            optimizer.state_dict()
                        ),
                    },
                    checkpoint_path,
                )

        if verbose and (
            epoch == 1
            or epoch % log_every == 0
            or is_best
        ):
            best_marker = (
                " | MEJOR"
                if is_best
                else ""
            )

            print(
                f"epoch {epoch:03d}/{epochs} | "
                f"train={train_loss:.4f} | "
                f"val={val_loss:.4f} | "
                f"p_value={val_parts['p_value']:.3f} | "
                f"p<=10mm="
                f"{100 * val_parts['p_within_10']:.1f}% | "
                f"stiffener="
                f"{val_parts['stiffener_value']:.3f} | "
                f"presence="
                f"{val_parts['masked_presence']:.3f} | "
                f"n_alma="
                f"{val_parts['n_alma']:.3f} | "
                f"n_cantonera="
                f"{val_parts['n_cantonera']:.3f}"
                f"{best_marker}"
            )

    if best_state is None:
        raise RuntimeError(
            "No se pudo guardar ningún estado "
            "del modelo."
        )

    model.load_state_dict(
        best_state
    )

    if verbose:
        print(
            f"Mejor val_loss={best_val:.4f} "
            f"en la época "
            f"{history['best_epoch']}. "
            "Los mejores pesos se han restaurado."
        )

    return history


@torch.no_grad()
def forward_numpy(
    model,
    x_cat,
    x_num,
    device,
    p_transition_idx=None,
):
    """
    Forward sobre arrays o tensores.

    Si p_transition_idx es None, el modelo deriva las transiciones
    de los conteos predichos.
    """
    model.eval()

    x_cat_tensor = torch.as_tensor(
        x_cat,
        dtype=torch.long,
        device=device,
    )

    x_num_tensor = torch.as_tensor(
        x_num,
        dtype=torch.float32,
        device=device,
    )

    if p_transition_idx is not None:
        transition_tensor = (
            torch.as_tensor(
                p_transition_idx,
                dtype=torch.long,
                device=device,
            )
        )
    else:
        transition_tensor = None

    predictions = model(
        x_cat=x_cat_tensor,
        x_num=x_num_tensor,
        p_transition_idx=transition_tensor,
    )

    return {
        key: value.detach().cpu().numpy()
        for key, value
        in predictions.items()
    }


def predict_loader(
    model,
    loader,
    device,
    use_true_transitions=False,
):
    """
    Predice todos los batches.

    Por defecto utiliza los conteos predichos y reproduce inferencia
    real de producción.

    use_true_transitions=True permite medir el techo de la regresión
    cuando la topología es correcta.
    """
    outputs = []

    for batch in loader:
        transition_idx = (
            batch["p_transition_idx"]
            if use_true_transitions
            else None
        )

        batch_output = forward_numpy(
            model=model,
            x_cat=batch["x_cat"],
            x_num=batch["x_num"],
            device=device,
            p_transition_idx=transition_idx,
        )

        outputs.append(
            batch_output
        )

    if not outputs:
        raise RuntimeError(
            "El DataLoader no produjo predicciones."
        )

    return {
        key: np.concatenate(
            [
                output[key]
                for output in outputs
            ],
            axis=0,
        )
        for key in outputs[0]
    }


def outputs_to_design(
    outputs,
    preprocessor,
):
    """
    Convierte las salidas crudas en un diseño físico.
    """
    design = decode_predictions(
        reg_always_real=(
            preprocessor.inverse_reg_always(
                outputs["reg_always"]
            )
        ),
        masked_value_real=(
            preprocessor.inverse_masked(
                outputs["masked_value"]
            )
        ),
        masked_presence_prob=(
            _sigmoid(
                outputs[
                    "masked_presence_logit"
                ]
            )
        ),
        bolt_logits=(
            outputs["bolt_logits"]
        ),
        n_alma_logits=(
            outputs["n_alma_logits"]
        ),
        n_cantonera_logits=(
            outputs[
                "n_cantonera_logits"
            ]
        ),
        standard_logits=(
            outputs["standard_logits"]
        ),
        standard_classes=(
            preprocessor
            .standard_encoder
            .classes_
        ),
        slip_critical_logit=(
            outputs[
                "slip_critical_logit"
            ]
        ),
    )

    return derive_dependent_columns(
        design
    )