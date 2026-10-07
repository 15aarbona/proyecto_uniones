import torch
import torch.nn as nn
import torch.nn.functional as F
from .config import N_Y

def _per_column_mean(values, mask):
    mask = mask.float()
    count = mask.sum(0)
    per_col = (values * mask).sum(0) / count.clamp_min(1.0)
    available = count > 0
    return per_col[available].mean() if available.any() else values.sum() * 0.0

class ConnectionDesignLoss(nn.Module):
    def __init__(self, w_cls=1.0, w_counts=1.0, w_reg=1.0,
                 w_p_value=2.0, w_p_cumulative=0.5,
                 w_stiffener_value=1.0, w_masked_presence=0.5,
                 n_alma_weights=None, n_cantonera_weights=None,
                 presence_pos_weight=None, p_std_mm=None,
                 p_tolerance_mm=10.0):
        super().__init__()
        self.w_cls = w_cls
        self.w_counts = w_counts
        self.w_reg = w_reg
        self.w_p_value = w_p_value
        self.w_p_cumulative = w_p_cumulative
        self.w_stiffener_value = w_stiffener_value
        self.w_masked_presence = w_masked_presence
        self.p_tolerance_mm = p_tolerance_mm
        self.register_buffer("w_n_alma", None if n_alma_weights is None else torch.as_tensor(n_alma_weights, dtype=torch.float32))
        self.register_buffer("w_n_cantonera", None if n_cantonera_weights is None else torch.as_tensor(n_cantonera_weights, dtype=torch.float32))
        self.register_buffer("presence_pos_weight", None if presence_pos_weight is None else torch.as_tensor(presence_pos_weight, dtype=torch.float32))
        self.register_buffer("p_std_mm", None if p_std_mm is None else torch.as_tensor(p_std_mm, dtype=torch.float32))
        self.ce = nn.CrossEntropyLoss()
        self.bce = nn.BCEWithLogitsLoss()
        self.huber = nn.SmoothL1Loss(reduction="none", beta=1.0)

    def forward(self, preds, targets):
        loss_standard = self.ce(preds["standard_logits"], targets["standard_idx"])
        loss_bolt = self.ce(preds["bolt_logits"], targets["bolt_idx"])
        loss_slip = self.bce(preds["slip_critical_logit"], targets["slip_critical"])
        loss_cls = loss_standard + loss_bolt + loss_slip
        loss_na = F.cross_entropy(preds["n_alma_logits"], targets["n_alma_idx"], weight=self.w_n_alma)
        loss_nc = F.cross_entropy(preds["n_cantonera_logits"], targets["n_cantonera_idx"], weight=self.w_n_cantonera)
        loss_counts = loss_na + loss_nc
        loss_reg = self.huber(preds["reg_always"], targets["reg_always"]).mean()

        mask = targets["masked_mask"]
        p_mask = mask[:, :N_Y]
        stiff_mask = mask[:, N_Y:]
        p_pred = preds["masked_value"][:, :N_Y]
        p_true = targets["masked_value"][:, :N_Y]
        stiff_pred = preds["masked_value"][:, N_Y:]
        stiff_true = targets["masked_value"][:, N_Y:]
        loss_p = _per_column_mean(self.huber(p_pred, p_true), p_mask)
        loss_stiff = _per_column_mean(self.huber(stiff_pred, stiff_true), stiff_mask)

        # Cumulative geometry loss in standardized space; masked at each active endpoint.
        cumulative_pred = torch.cumsum(p_pred, dim=1)
        cumulative_true = torch.cumsum(p_true, dim=1)
        loss_cumulative = _per_column_mean(self.huber(cumulative_pred, cumulative_true), p_mask)

        presence = F.binary_cross_entropy_with_logits(
            preds["masked_presence_logit"], mask,
            pos_weight=self.presence_pos_weight, reduction="none"
        ).mean(0).mean()

        with torch.no_grad():
            if self.p_std_mm is not None:
                error_mm = (p_pred - p_true) * self.p_std_mm[:N_Y].unsqueeze(0)
                denom = p_mask.sum().clamp_min(1.0)
                within10 = (((error_mm.abs() <= self.p_tolerance_mm).float()) * p_mask).sum() / denom
            else:
                within10 = p_pred.sum() * 0.0

        total = (self.w_cls*loss_cls + self.w_counts*loss_counts + self.w_reg*loss_reg
                 + self.w_p_value*loss_p + self.w_p_cumulative*loss_cumulative
                 + self.w_stiffener_value*loss_stiff + self.w_masked_presence*presence)
        parts = {
            "standard": loss_standard.item(), "bolt": loss_bolt.item(),
            "slip_critical": loss_slip.item(), "n_alma": loss_na.item(),
            "n_cantonera": loss_nc.item(), "reg_always": loss_reg.item(),
            "p_value": loss_p.item(), "p_cumulative": loss_cumulative.item(),
            "stiffener_value": loss_stiff.item(), "masked_presence": presence.item(),
            "p_within_10": within10.item(),
        }
        return total, parts
