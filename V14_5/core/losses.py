"""Perdida multitarea para la ablacion autorregresiva v3."""

import torch
import torch.nn as nn
import torch.nn.functional as F

from .config import N_Y, N_CANTONERA_CLASSES, REGRESSION_ALWAYS


def per_column_mean(values, mask):
    mask = mask.float()
    n_active = mask.sum(dim=0)
    per_column = (values * mask).sum(dim=0) / n_active.clamp_min(1.0)
    available = n_active > 0
    if available.any():
        return per_column[available].mean()
    return values.sum() * 0.0


class ConnectionDesignLoss(nn.Module):
    def __init__(
        self,
        n_alma_weights,
        n_cantonera_weights,
        presence_pos_weight,
        p_mean_mm,
        p_std_mm,
        w_cls=1.0,
        w_counts=1.0,
        w_reg=1.0,
        w_p_value=2.0,
        w_p_cumulative=0.1,
        w_stiffener_value=1.0,
        w_masked_presence=0.5,
        cumulative_scale_mm=20.0,
        p_tolerance_mm=10.0,
    ):
        super().__init__()
        self.w_cls = float(w_cls)
        self.w_counts = float(w_counts)
        self.w_reg = float(w_reg)
        self.w_p_value = float(w_p_value)
        self.w_p_cumulative = float(w_p_cumulative)
        self.w_stiffener_value = float(w_stiffener_value)
        self.w_masked_presence = float(w_masked_presence)
        self.cumulative_scale_mm = float(cumulative_scale_mm)
        self.p_tolerance_mm = float(p_tolerance_mm)

        self.register_buffer(
            "n_alma_weights",
            torch.as_tensor(n_alma_weights, dtype=torch.float32),
        )
        self.register_buffer(
            "n_cantonera_weights",
            torch.as_tensor(n_cantonera_weights, dtype=torch.float32),
        )
        self.register_buffer(
            "presence_pos_weight",
            torch.as_tensor(presence_pos_weight, dtype=torch.float32),
        )
        self.register_buffer(
            "p_mean_mm",
            torch.as_tensor(p_mean_mm, dtype=torch.float32).view(1, N_Y),
        )
        self.register_buffer(
            "p_std_mm",
            torch.as_tensor(p_std_mm, dtype=torch.float32).view(1, N_Y),
        )

        self.huber = nn.SmoothL1Loss(reduction="none", beta=1.0)

    def forward(self, outputs, targets):
        loss_standard = F.cross_entropy(
            outputs["standard_logits"],
            targets["standard_idx"],
        )
        loss_bolt = F.cross_entropy(
            outputs["bolt_logits"],
            targets["bolt_idx"],
        )
        loss_slip = F.binary_cross_entropy_with_logits(
            outputs["slip_critical_logit"],
            targets["slip_critical"],
        )
        loss_classification = loss_standard + loss_bolt + loss_slip

        has_count_heads = (
            "n_alma_logits" in outputs and "n_cantonera_logits" in outputs
        )
        if has_count_heads:
            loss_n_alma = F.cross_entropy(
                outputs["n_alma_logits"],
                targets["n_alma_idx"],
                weight=self.n_alma_weights,
            )
            loss_n_cantonera = F.cross_entropy(
                outputs["n_cantonera_logits"],
                targets["n_cantonera_idx"],
                weight=self.n_cantonera_weights,
            )
        else:
            loss_n_alma = outputs["reg_always"].sum() * 0.0
            loss_n_cantonera = outputs["reg_always"].sum() * 0.0
        loss_counts = loss_n_alma + loss_n_cantonera

        loss_reg_always = self.huber(
            outputs["reg_always"],
            targets["reg_always"],
        ).mean()

        mask = targets["masked_mask"]
        p_mask = mask[:, :N_Y]
        stiffener_mask = mask[:, N_Y:]

        p_pred = outputs["masked_value"][:, :N_Y]
        p_true = targets["masked_value"][:, :N_Y]
        stiffener_pred = outputs["masked_value"][:, N_Y:]
        stiffener_true = targets["masked_value"][:, N_Y:]

        loss_p_value = per_column_mean(
            self.huber(p_pred, p_true),
            p_mask,
        )
        loss_stiffener_value = per_column_mean(
            self.huber(stiffener_pred, stiffener_true),
            stiffener_mask,
        )

        p_pred_mm = p_pred * self.p_std_mm + self.p_mean_mm
        p_true_mm = p_true * self.p_std_mm + self.p_mean_mm
        cumulative_pred_mm = torch.cumsum(p_pred_mm, dim=1)
        cumulative_true_mm = torch.cumsum(p_true_mm, dim=1)

        loss_p_cumulative = per_column_mean(
            self.huber(
                cumulative_pred_mm / self.cumulative_scale_mm,
                cumulative_true_mm / self.cumulative_scale_mm,
            ),
            p_mask,
        )

        presence_values = F.binary_cross_entropy_with_logits(
            outputs["masked_presence_logit"],
            mask,
            pos_weight=self.presence_pos_weight,
            reduction="none",
        )
        loss_presence = presence_values.mean(dim=0).mean()

        with torch.no_grad():
            p_error_mm = torch.abs(p_pred_mm - p_true_mm)
            n_active = p_mask.sum().clamp_min(1.0)
            p_within_10 = (
                ((p_error_mm <= self.p_tolerance_mm).float() * p_mask).sum()
                / n_active
            )
            p_mae_mm = (p_error_mm * p_mask).sum() / n_active
            cumulative_mae_mm = (
                torch.abs(cumulative_pred_mm - cumulative_true_mm) * p_mask
            ).sum() / n_active

        with torch.no_grad():
            if has_count_heads:
                topology_exact = (
                    (outputs["n_alma_logits"].argmax(dim=1) == targets["n_alma_idx"])
                    & (
                        outputs["n_cantonera_logits"].argmax(dim=1)
                        == targets["n_cantonera_idx"]
                    )
                ).float().mean()
            else:
                topology_exact = outputs["reg_always"].sum() * 0.0

        total = (
            self.w_cls * loss_classification
            + self.w_counts * loss_counts
            + self.w_reg * loss_reg_always
            + self.w_p_value * loss_p_value
            + self.w_p_cumulative * loss_p_cumulative
            + self.w_stiffener_value * loss_stiffener_value
            + self.w_masked_presence * loss_presence
        )

        parts = {
            "standard": loss_standard.item(),
            "bolt": loss_bolt.item(),
            "slip_critical": loss_slip.item(),
            "n_alma": loss_n_alma.item(),
            "n_cantonera": loss_n_cantonera.item(),
            "reg_always": loss_reg_always.item(),
            "p_value": loss_p_value.item(),
            "p_cumulative": loss_p_cumulative.item(),
            "p_within_10": p_within_10.item(),
            "p_mae_mm": p_mae_mm.item(),
            "cumulative_mae_mm": cumulative_mae_mm.item(),
            "stiffener_value": loss_stiffener_value.item(),
            "masked_presence": loss_presence.item(),
            "topology_exact": topology_exact.item(),
        }
        return total, parts


# =============================================================================
# V4: perdida para la cabeza de p discretizada (+ topologia conjunta opcional)
# =============================================================================


class ConnectionDesignLossV4(ConnectionDesignLoss):
    """Hereda la perdida v3 (clasificacion, reg_always, rigidizadores y las
    metricas p_within_10 / p_mae_mm / cumulative_mae_mm) y:

    * anula los terminos de regresion de p y los sustituye por una cross-entropy
      ORDINAL sobre la rejilla de 5 mm, promediada por separacion activa
      (coincide con la metrica, a diferencia del promedio por columna);
    * aplica la perdida de presencia solo a los rigidizadores (la presencia de
      p no se usa en inferencia: mandan los conteos);
    * si joint_topology=True, sustituye la perdida de conteos por una unica
      cross-entropy sobre (n_alma, n_cantonera);

    label_scale_bins: escala (en bins) del suavizado Laplace de la etiqueta.
        1.0 -> la probabilidad cae a 1/e a 5 mm del valor real. Penaliza menos
        fallar por 1 bin que por 5. Con ~0.05 las etiquetas son casi duras.
    """

    def __init__(
        self,
        *args,
        n_p_bins,
        p_bin_step_mm=5.0,
        w_p_ce=2.0,
        label_scale_bins=1.0,
        joint_topology=False,
        **kwargs,
    ):
        original_w_counts = float(kwargs.get("w_counts", 1.0))
        original_w_presence = float(kwargs.get("w_masked_presence", 0.5))
        kwargs["w_p_value"] = 0.0
        kwargs["w_p_cumulative"] = 0.0
        kwargs["w_masked_presence"] = 0.0
        if joint_topology:
            kwargs["w_counts"] = 0.0
        super().__init__(*args, **kwargs)

        self.w_p_ce = float(w_p_ce)
        self.p_bin_step_mm = float(p_bin_step_mm)
        self.label_scale_bins = float(label_scale_bins)
        self.joint_topology = bool(joint_topology)
        self.w_topology = original_w_counts if joint_topology else 0.0
        self.w_presence_stiffeners = original_w_presence
        self.register_buffer("bin_index", torch.arange(int(n_p_bins), dtype=torch.float32))

    def forward(self, outputs, targets):
        total, parts = super().forward(outputs, targets)

        # --- p: cross-entropy ordinal sobre la rejilla ---
        p_logits = outputs["p_logits"]  # (B, N_Y, K)
        p_mask = targets["masked_mask"][:, :N_Y]
        p_true_mm = targets["masked_value"][:, :N_Y] * self.p_std_mm + self.p_mean_mm
        n_bins = p_logits.shape[-1]
        target_bin = (p_true_mm / self.p_bin_step_mm).round().clamp(0, n_bins - 1)

        distance = (self.bin_index.view(1, 1, -1) - target_bin.unsqueeze(-1)).abs()
        soft_target = torch.exp(-distance / max(self.label_scale_bins, 1e-3))
        soft_target = soft_target / soft_target.sum(dim=-1, keepdim=True)

        ce = -(soft_target * F.log_softmax(p_logits, dim=-1)).sum(dim=-1)  # (B, N_Y)
        loss_p_ce = (ce * p_mask).sum() / p_mask.sum().clamp_min(1.0)
        total = total + self.w_p_ce * loss_p_ce
        parts["p_ce"] = loss_p_ce.item()

        # --- presencia: solo rigidizadores ---
        mask = targets["masked_mask"]
        presence_values = F.binary_cross_entropy_with_logits(
            outputs["masked_presence_logit"][:, N_Y:],
            mask[:, N_Y:],
            pos_weight=self.presence_pos_weight[N_Y:],
            reduction="none",
        )
        loss_presence = presence_values.mean(dim=0).mean()
        total = total + self.w_presence_stiffeners * loss_presence
        parts["masked_presence"] = loss_presence.item()

        # --- topologia ---
        if self.joint_topology:
            joint_target = (
                targets["n_alma_idx"] * N_CANTONERA_CLASSES + targets["n_cantonera_idx"]
            )
            loss_topology = F.cross_entropy(outputs["topology_logits"], joint_target)
            total = total + self.w_topology * loss_topology
            parts["topology"] = loss_topology.item()

        return total, parts


class ConnectionDesignLossV14(ConnectionDesignLoss):
    """Perdida V14: p ordinal + filas totales + conteos geometricos.

    No hay cabezas de n_alma/n_cantonera. La cabeza ``n_rows`` solo fija la
    longitud de la secuencia; los conteos se calculan desde las distancias p y
    la geometria de la viga.
    """

    def __init__(
        self,
        *args,
        n_p_bins,
        p_bin_step_mm=5.0,
        w_p_ce=2.0,
        label_scale_bins=1.0,
        w_geom_counts=1.0,
        w_top=0.5,
        w_bottom=0.5,
        w_total_rows=0.5,
        w_flange=0.5,
        w_has_cantonera=0.5,
        temperature_mm=2.5,
        reg_mean_mm=None,
        reg_std_mm=None,
        **kwargs,
    ):
        kwargs["w_counts"] = 0.0
        kwargs["w_p_value"] = 0.0
        kwargs["w_p_cumulative"] = 0.0
        kwargs["w_masked_presence"] = 0.0
        super().__init__(*args, **kwargs)

        self.w_p_ce = float(w_p_ce)
        self.w_geom_counts = float(w_geom_counts)
        self.w_top = float(w_top)
        self.w_bottom = float(w_bottom)
        self.w_total_rows = float(w_total_rows)
        self.w_flange = float(w_flange)
        self.w_has_cantonera = float(w_has_cantonera)
        self.temperature_mm = float(temperature_mm)
        self.p_bin_step_mm = float(p_bin_step_mm)
        self.label_scale_bins = float(label_scale_bins)
        self.register_buffer("bin_index", torch.arange(int(n_p_bins), dtype=torch.float32))
        self.register_buffer(
            "reg_mean_mm",
            torch.as_tensor(
                reg_mean_mm if reg_mean_mm is not None else [0.0] * len(REGRESSION_ALWAYS),
                dtype=torch.float32,
            ).view(1, -1),
        )
        self.register_buffer(
            "reg_std_mm",
            torch.as_tensor(
                reg_std_mm if reg_std_mm is not None else [1.0] * len(REGRESSION_ALWAYS),
                dtype=torch.float32,
            ).view(1, -1),
        )

    def forward(self, outputs, targets):
        total, parts = super().forward(outputs, targets)

        p_logits = outputs["p_logits"]
        p_mask = targets["masked_mask"][:, :N_Y]
        p_true_mm = targets["masked_value"][:, :N_Y] * self.p_std_mm + self.p_mean_mm

        n_bins = p_logits.shape[-1]
        target_bin = (p_true_mm / self.p_bin_step_mm).round().clamp(0, n_bins - 1)
        distance = (self.bin_index.view(1, 1, -1) - target_bin.unsqueeze(-1)).abs()
        soft_target = torch.exp(-distance / max(self.label_scale_bins, 1e-3))
        soft_target = soft_target / soft_target.sum(dim=-1, keepdim=True)
        ce = -(soft_target * F.log_softmax(p_logits, dim=-1)).sum(dim=-1)
        loss_p_ce = (ce * p_mask).sum() / p_mask.sum().clamp_min(1.0)
        total = total + self.w_p_ce * loss_p_ce
        parts["p_ce"] = loss_p_ce.item()

        loss_n_rows = F.cross_entropy(outputs["n_rows_logits"], targets["n_rows_idx"])
        loss_has_cantonera = F.binary_cross_entropy_with_logits(
            outputs["has_cantonera_logit"], targets["has_cantonera"]
        )
        total = total + loss_n_rows + self.w_has_cantonera * loss_has_cantonera
        parts["n_rows"] = loss_n_rows.item()
        parts["has_cantonera"] = loss_has_cantonera.item()

        reg = outputs["reg_always"] * self.reg_std_mm + self.reg_mean_mm
        idx_e = REGRESSION_ALWAYS.index("e")
        idx_d = REGRESSION_ALWAYS.index("d")
        e = reg[:, idx_e : idx_e + 1]
        d = reg[:, idx_d : idx_d + 1]

        p_pred_mm = outputs["p_mode_mm"] * p_mask
        rows = torch.cat([e, e + torch.cumsum(p_pred_mm, dim=1)], dim=1)
        row_active = torch.cat([torch.ones_like(e), p_mask], dim=1)

        beam_d = targets["beam_d_mm"].view(-1, 1)
        beam_tf = targets["beam_tf_mm"].view(-1, 1)
        top_out = e + d
        top_in = top_out + beam_tf
        bot_out = top_out + beam_d
        bot_in = bot_out - beam_tf
        l_h = targets["lh_mm"].view(-1, 1).clamp_min(0.0)
        angle_bottom = bot_out + l_h

        tau = max(self.temperature_mm, 1e-3)
        sig = torch.sigmoid
        above = sig((top_out - rows) / tau)
        web = sig((rows - top_in) / tau) * sig((bot_in - rows) / tau)
        cant = sig((rows - bot_out) / tau) * sig((angle_bottom - rows) / tau)
        bottom = sig((rows - angle_bottom) / tau)
        flange_top = sig((rows - top_out) / tau) * sig((top_in - rows) / tau)
        flange_bot = sig((rows - bot_in) / tau) * sig((bot_out - rows) / tau)
        flange = flange_top + flange_bot

        n_top = (above * row_active).sum(dim=1)
        n_alma = (web * row_active).sum(dim=1)
        n_cant = (cant * row_active).sum(dim=1)
        n_bottom = (bottom * row_active).sum(dim=1)
        n_flange = (flange * row_active).sum(dim=1)
        n_rows = row_active.sum(dim=1)

        na_true = targets["n_alma_idx"].float()
        nc_true_flat = targets["n_cantonera_idx"].float()
        rows_true = targets["n_rows_idx"].float()

        loss_alma = F.smooth_l1_loss(n_alma, na_true)
        loss_cant = F.smooth_l1_loss(n_cant, nc_true_flat)
        loss_top = F.smooth_l1_loss(n_top, torch.ones_like(n_top))
        loss_bottom = F.smooth_l1_loss(n_bottom, torch.ones_like(n_bottom))
        loss_total_rows = F.smooth_l1_loss(n_rows, rows_true)
        loss_flange = F.smooth_l1_loss(n_flange, torch.zeros_like(n_flange))

        total = (
            total
            + self.w_geom_counts * (loss_alma + loss_cant)
            + self.w_top * loss_top
            + self.w_bottom * loss_bottom
            + self.w_total_rows * loss_total_rows
            + self.w_flange * loss_flange
        )

        with torch.no_grad():
            geometry_exact = (
                (n_alma.round() == na_true)
                & (n_cant.round() == nc_true_flat)
                & (n_top.round() == 1)
                & (n_bottom.round() == 1)
            ).float().mean()
            n_rows_exact = (
                outputs["n_rows_logits"].argmax(dim=1) == targets["n_rows_idx"]
            ).float().mean()
            top_ok = (n_top.round() == 1).float().mean()
            bottom_ok = (n_bottom.round() == 1).float().mean()
            has_cantonera_exact = (
                (torch.sigmoid(outputs["has_cantonera_logit"]) >= 0.5)
                == (targets["has_cantonera"] >= 0.5)
            ).float().mean()

        parts.update({
            "geom_alma": loss_alma.item(),
            "geom_cantonera": loss_cant.item(),
            "geom_top": loss_top.item(),
            "geom_bottom": loss_bottom.item(),
            "geom_total_rows": loss_total_rows.item(),
            "geom_flange": loss_flange.item(),
            "geometry_exact": geometry_exact.item(),
            "n_rows_exact": n_rows_exact.item(),
            "top_ok": top_ok.item(),
            "bottom_ok": bottom_ok.item(),
            "has_cantonera_exact": has_cantonera_exact.item(),
        })
        return total, parts
