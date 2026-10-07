import torch
import torch.nn as nn
import torch.nn.functional as F


def _per_column_mean(values, mask):
    """
    values, mask: (B, C). Media sobre las muestras ACTIVAS de cada columna y luego media
    sobre las columnas con algún activo en el batch. Así las columnas raras (p11, p12,
    tws en la práctica) pesan igual que las frecuentes, en vez de diluirse en un
    promedio global.
    """
    n_active = mask.sum(dim=0)
    per_col = (values * mask).sum(dim=0) / n_active.clamp_min(1.0)
    has_any = n_active > 0
    if has_any.any():
        return per_col[has_any].mean()
    return values.sum() * 0.0  # sin activos en el batch: pérdida 0 con gradiente válido


class ConnectionDesignLoss(nn.Module):
    """
    Componentes:
      cls        : CE(standard) + CE(Bolt) + BCE(SlipCritical)
      counts     : CE ponderada por frecuencia inversa de n_alma y n_cantonera
                   (desbalanceados: los valores altos son mucho menos probables)
      reg_always : Huber sobre g, e, d, Bp, tp, Lh (estandarizados)
      masked_value    : Huber, solo en muestras activas, promediado por columna
                        (MASKED_COLUMNS = p1..p12, tws, ts, tbs, tst)
      masked_presence : BCE de existencia, una por columna (las p activas son siempre
                        un prefijo; el conteo n_alma+n_cantonera lo determina y el
                        post-proceso fuerza el prefijo)

    Sin penalizaciones geométricas ni de orden: cada Y es una cota acumulada creciente
    por construcción del dato, y el nº de Ys activas queda fijado por los conteos.
    """

    def __init__(self, w_cls=1.0, w_counts=1.0, w_reg=1.0, w_masked_value=2.0,
                 w_masked_presence=1.0, w_role=0.5, n_alma_weights=None, n_cantonera_weights=None,
                 presence_pos_weight=None, role_weights=None):
        super().__init__()
        self.w_cls, self.w_counts, self.w_reg = w_cls, w_counts, w_reg
        self.w_masked_value, self.w_masked_presence = w_masked_value, w_masked_presence
        self.w_role = w_role
        # buffers: viajan con .to(device) junto al resto del módulo
        self.register_buffer(
            "w_n_alma",
            None if n_alma_weights is None else torch.as_tensor(n_alma_weights, dtype=torch.float32),
        )
        self.register_buffer(
            "w_n_cantonera",
            None if n_cantonera_weights is None else torch.as_tensor(n_cantonera_weights, dtype=torch.float32),
        )
        # pos_weight de presencia por columna (frecuencia inversa); None => todo 1.
        self.register_buffer(
            "presence_pos_weight",
            None if presence_pos_weight is None else torch.as_tensor(presence_pos_weight, dtype=torch.float32),
        )
        self.register_buffer(
            "role_class_weights",
            None if role_weights is None else torch.as_tensor(role_weights, dtype=torch.float32),
        )
        self.ce = nn.CrossEntropyLoss()
        self.bce = nn.BCEWithLogitsLoss()
        self.huber = nn.SmoothL1Loss(reduction="none", beta=1.0)

    def _bce_presence(self, logits, target):
        """BCE de presencia con pos_weight por columna y reducción media por columna,
        para que las columnas raras (tws) no se ahoguen en el mar de ceros."""
        bce = F.binary_cross_entropy_with_logits(
            logits, target, pos_weight=self.presence_pos_weight, reduction="none")
        per_col = bce.mean(dim=0)
        return per_col.mean()

    def forward(self, preds, targets):
        loss_standard = self.ce(preds["standard_logits"], targets["standard_idx"])
        loss_bolt = self.ce(preds["bolt_logits"], targets["bolt_idx"])
        loss_slip = self.bce(preds["slip_critical_logit"], targets["slip_critical"])
        loss_cls = loss_standard + loss_bolt + loss_slip

        loss_n_alma = F.cross_entropy(preds["n_alma_logits"], targets["n_alma_idx"],
                                      weight=self.w_n_alma)
        loss_n_cantonera = F.cross_entropy(preds["n_cantonera_logits"], targets["n_cantonera_idx"],
                                           weight=self.w_n_cantonera)
        loss_counts = loss_n_alma + loss_n_cantonera

        loss_reg_always = torch.mean(self.huber(preds["reg_always"], targets["reg_always"]))

        mask = targets["masked_mask"]
        loss_masked_value = _per_column_mean(
            self.huber(preds["masked_value"], targets["masked_value"]), mask)
        loss_masked_presence = self._bce_presence(preds["masked_presence_logit"], mask)

        # Rol geométrico por paso (auxiliar): CE sobre pasos activos (ignore_index).
        if "role_logits" in preds and "role_idx" in targets:
            loss_role = F.cross_entropy(
                preds["role_logits"].reshape(-1, preds["role_logits"].shape[-1]),
                targets["role_idx"].reshape(-1),
                weight=self.role_class_weights, ignore_index=-100)
        else:
            loss_role = preds["reg_always"].sum() * 0.0

        total = (
            self.w_cls * loss_cls
            + self.w_counts * loss_counts
            + self.w_reg * loss_reg_always
            + self.w_masked_value * loss_masked_value
            + self.w_masked_presence * loss_masked_presence
            + self.w_role * loss_role
        )

        parts = {
            "standard": loss_standard.item(),
            "bolt": loss_bolt.item(),
            "slip_critical": loss_slip.item(),
            "n_alma": loss_n_alma.item(),
            "n_cantonera": loss_n_cantonera.item(),
            "reg_always": loss_reg_always.item(),
            "masked_value": loss_masked_value.item(),
            "masked_presence": loss_masked_presence.item(),
            "role": loss_role.item(),
        }
        return total, parts
