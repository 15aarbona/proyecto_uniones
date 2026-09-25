import torch
import torch.nn as nn


def _per_column_mean(values, mask):
    """
    values, mask: (B, C). Media sobre las muestras ACTIVAS de cada columna y luego media
    sobre las columnas con algún activo en el batch. Así las columnas raras (C_4, C_5, p9+
    en la versión anterior) pesan igual que las frecuentes, en vez de diluirse en un
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
      cls        : CE(DrawingCode) + CE(Bolt) + BCE(SlipCritical)
      reg_always : Huber sobre g, e, d, Bp, Lp, tp (estandarizados)
      masked_value    : Huber, solo en muestras activas, promediado por columna
                        (MASKED_COLUMNS = E-S, D_1..5, I-C, C_1..5, E-C, tws, ts, tbs, tst)
      masked_presence : BCE de existencia, una por columna

    Sin penalizaciones geométricas ni de orden (se quitaron en la v2: se calculaban con
    tensores desconectados del grafo -sin gradiente- y "p1<=p2<=..." no se cumplía en los
    datos reales; con la descomposición en E-S/D/I-C/C/E-C esa restricción de orden ya no
    tiene sentido, cada columna es una cantidad distinta, no una secuencia).
    """

    def __init__(self, w_cls=1.0, w_reg=1.0, w_masked_value=2.0, w_masked_presence=1.0):
        super().__init__()
        self.w_cls, self.w_reg = w_cls, w_reg
        self.w_masked_value, self.w_masked_presence = w_masked_value, w_masked_presence
        self.ce = nn.CrossEntropyLoss()
        self.bce = nn.BCEWithLogitsLoss()
        self.huber = nn.SmoothL1Loss(reduction="none", beta=1.0)

    def forward(self, preds, targets):
        loss_drawing = self.ce(preds["drawing_code_logits"], targets["drawing_code_idx"])
        loss_bolt = self.ce(preds["bolt_logits"], targets["bolt_idx"])
        loss_slip = self.bce(preds["slip_critical_logit"], targets["slip_critical"])
        loss_cls = loss_drawing + loss_bolt + loss_slip

        loss_reg_always = torch.mean(self.huber(preds["reg_always"], targets["reg_always"]))

        mask = targets["masked_mask"]
        loss_masked_value = _per_column_mean(
            self.huber(preds["masked_value"], targets["masked_value"]), mask)
        loss_masked_presence = self.bce(preds["masked_presence_logit"], mask)

        total = (
            self.w_cls * loss_cls
            + self.w_reg * loss_reg_always
            + self.w_masked_value * loss_masked_value
            + self.w_masked_presence * loss_masked_presence
        )

        parts = {
            "drawing_code": loss_drawing.item(),
            "bolt": loss_bolt.item(),
            "slip_critical": loss_slip.item(),
            "reg_always": loss_reg_always.item(),
            "masked_value": loss_masked_value.item(),
            "masked_presence": loss_masked_presence.item(),
        }
        return total, parts
