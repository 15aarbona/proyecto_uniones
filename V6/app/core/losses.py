"""
Funciones de pérdida del modelo.

La loss combina:

    - clasificación global;
    - conteos de filas;
    - regresiones siempre activas;
    - separaciones p;
    - rigidizadores;
    - presencia auxiliar.

Las p y los rigidizadores se calculan por separado para poder
monitorizar sus pérdidas independientemente.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

from .config import N_Y


def _per_column_mean(
    values,
    mask,
):
    """
    Media sobre muestras activas de cada columna y después media
    sobre las columnas con al menos una muestra activa.

    Esto evita que las columnas frecuentes dominen automáticamente
    a las columnas menos frecuentes.
    """
    mask = mask.float()

    n_active = mask.sum(dim=0)

    per_column = (
        (values * mask).sum(dim=0)
        / n_active.clamp_min(1.0)
    )

    has_any = n_active > 0

    if has_any.any():
        return per_column[
            has_any
        ].mean()

    return values.sum() * 0.0


class ConnectionDesignLoss(nn.Module):
    """
    Función de pérdida multitarea.
    """

    def __init__(
        self,
        w_cls=1.0,
        w_counts=1.0,
        w_reg=1.0,
        w_p_value=2.0,
        w_stiffener_value=1.0,
        w_masked_presence=0.5,
        n_alma_weights=None,
        n_cantonera_weights=None,
        presence_pos_weight=None,
        p_std_mm=None,
        p_tolerance_mm=10.0,
    ):
        super().__init__()

        self.w_cls = float(w_cls)
        self.w_counts = float(w_counts)
        self.w_reg = float(w_reg)
        self.w_p_value = float(w_p_value)
        self.w_stiffener_value = float(
            w_stiffener_value
        )
        self.w_masked_presence = float(
            w_masked_presence
        )

        self.p_tolerance_mm = float(
            p_tolerance_mm
        )

        self.register_buffer(
            "w_n_alma",
            (
                None
                if n_alma_weights is None
                else torch.as_tensor(
                    n_alma_weights,
                    dtype=torch.float32,
                )
            ),
        )

        self.register_buffer(
            "w_n_cantonera",
            (
                None
                if n_cantonera_weights is None
                else torch.as_tensor(
                    n_cantonera_weights,
                    dtype=torch.float32,
                )
            ),
        )

        self.register_buffer(
            "presence_pos_weight",
            (
                None
                if presence_pos_weight is None
                else torch.as_tensor(
                    presence_pos_weight,
                    dtype=torch.float32,
                )
            ),
        )

        self.register_buffer(
            "p_std_mm",
            (
                None
                if p_std_mm is None
                else torch.as_tensor(
                    p_std_mm,
                    dtype=torch.float32,
                )
            ),
        )

        self.ce = nn.CrossEntropyLoss()

        self.bce = (
            nn.BCEWithLogitsLoss()
        )

        self.huber = nn.SmoothL1Loss(
            reduction="none",
            beta=1.0,
        )

    def _bce_presence(
        self,
        logits,
        target,
    ):
        """
        BCE de presencia con pos_weight por columna.
        """
        loss = (
            F.binary_cross_entropy_with_logits(
                logits,
                target,
                pos_weight=(
                    self.presence_pos_weight
                ),
                reduction="none",
            )
        )

        return loss.mean(dim=0).mean()

    def forward(
        self,
        preds,
        targets,
    ):
        # ---------------------------------------------------------------
        # Clasificaciones globales
        # ---------------------------------------------------------------

        loss_standard = self.ce(
            preds["standard_logits"],
            targets["standard_idx"],
        )

        loss_bolt = self.ce(
            preds["bolt_logits"],
            targets["bolt_idx"],
        )

        loss_slip = self.bce(
            preds["slip_critical_logit"],
            targets["slip_critical"],
        )

        loss_cls = (
            loss_standard
            + loss_bolt
            + loss_slip
        )

        # ---------------------------------------------------------------
        # Conteos
        # ---------------------------------------------------------------

        loss_n_alma = F.cross_entropy(
            preds["n_alma_logits"],
            targets["n_alma_idx"],
            weight=self.w_n_alma,
        )

        loss_n_cantonera = (
            F.cross_entropy(
                preds["n_cantonera_logits"],
                targets["n_cantonera_idx"],
                weight=self.w_n_cantonera,
            )
        )

        loss_counts = (
            loss_n_alma
            + loss_n_cantonera
        )

        # ---------------------------------------------------------------
        # Regresión global
        # ---------------------------------------------------------------

        loss_reg_always = torch.mean(
            self.huber(
                preds["reg_always"],
                targets["reg_always"],
            )
        )

        # ---------------------------------------------------------------
        # Valores con máscara
        # ---------------------------------------------------------------

        masked_pred = preds["masked_value"]
        masked_target = targets["masked_value"]
        masked_mask = targets["masked_mask"]

        p_pred = masked_pred[:, :N_Y]
        p_target = masked_target[:, :N_Y]
        p_mask = masked_mask[:, :N_Y]

        stiffener_pred = masked_pred[:, N_Y:]
        stiffener_target = masked_target[:, N_Y:]
        stiffener_mask = masked_mask[:, N_Y:]

        loss_p_value = _per_column_mean(
            self.huber(
                p_pred,
                p_target,
            ),
            p_mask,
        )

        if stiffener_pred.shape[1] > 0:
            loss_stiffener_value = (
                _per_column_mean(
                    self.huber(
                        stiffener_pred,
                        stiffener_target,
                    ),
                    stiffener_mask,
                )
            )
        else:
            loss_stiffener_value = (
                masked_pred.sum() * 0.0
            )

        # ---------------------------------------------------------------
        # Presencia auxiliar
        # ---------------------------------------------------------------

        loss_masked_presence = (
            self._bce_presence(
                preds[
                    "masked_presence_logit"
                ],
                masked_mask,
            )
        )

        # ---------------------------------------------------------------
        # Métrica ±10 mm
        # ---------------------------------------------------------------

        with torch.no_grad():
            if self.p_std_mm is not None:
                p_std = (
                    self.p_std_mm[:N_Y]
                    .unsqueeze(0)
                )

                p_error_mm = (
                    (p_pred - p_target)
                    * p_std
                )

                n_active = (
                    p_mask.sum()
                    .clamp_min(1.0)
                )

                p_within_10 = (
                    (
                        torch.abs(p_error_mm)
                        <= self.p_tolerance_mm
                    ).float()
                    * p_mask
                ).sum() / n_active

            else:
                p_within_10 = (
                    p_pred.sum() * 0.0
                )

        # ---------------------------------------------------------------
        # Total
        # ---------------------------------------------------------------

        total = (
            self.w_cls
            * loss_cls

            + self.w_counts
            * loss_counts

            + self.w_reg
            * loss_reg_always

            + self.w_p_value
            * loss_p_value

            + self.w_stiffener_value
            * loss_stiffener_value

            + self.w_masked_presence
            * loss_masked_presence
        )

        parts = {
            "standard": (
                loss_standard.item()
            ),
            "bolt": (
                loss_bolt.item()
            ),
            "slip_critical": (
                loss_slip.item()
            ),
            "n_alma": (
                loss_n_alma.item()
            ),
            "n_cantonera": (
                loss_n_cantonera.item()
            ),
            "reg_always": (
                loss_reg_always.item()
            ),
            "p_value": (
                loss_p_value.item()
            ),
            "stiffener_value": (
                loss_stiffener_value.item()
            ),
            "masked_presence": (
                loss_masked_presence.item()
            ),
            "p_within_10": (
                p_within_10.item()
            ),
        }

        return total, parts