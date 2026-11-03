"""Perdida PINN con Lagrangiano Aumentado (ALM): masa + penalizacion de restricciones.

Port de la celda 4 del notebook con UNA correccion de fondo:
  smooth_min original:  -(1/k) * log(exp(-k*a) + exp(-k*b) + 1e-8)
  Con a, b en kN (~100) exp(-k*a) subdesborda a 0 y el resultado queda clavado en
  -(1/k)*log(1e-8) = 1.84 para CUALQUIER diseno: F_row_Rd no dependia de tp ni del tornillo
  (gradiente 0) y la red solo podia cumplir flexion alargando brazos de palanca (e_x1 enorme)
  mientras la masa empujaba tp y bp a sus minimos. Ahora se usa logsumexp (estable).
Las formulas, restricciones C1..C5 e indices del vector de entrada (21) no cambian.
"""
import math

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

ROWS_TENSOR = [2, 3, 4, 5, 6]
MU_FIXED_EVAL = 1e5     # penalizacion estatica para comparar epocas/modelos


def static_score(mass: float, violations, mu: float = MU_FIXED_EVAL) -> float:
    """Metrica de seleccion independiente de los multiplicadores ALM."""
    v = np.maximum(0.0, np.asarray(violations, float))
    return float(mass + 0.5 * mu * np.sum(v ** 2))


class PhysicsInformedALMLoss(nn.Module):
    def __init__(self, num_constraints: int = 5, device="cpu", mu0: float = 10.0,
                 beta: float = 1.5, mu_max: float = 1e5, lambda_max: float = 1e6):
        super().__init__()
        self.device = device
        self.num_constraints = num_constraints
        self.lambdas = torch.zeros(num_constraints, device=device)
        self.mus = torch.full((num_constraints,), float(mu0), device=device)
        self.beta, self.mu_max, self.lambda_max = beta, mu_max, lambda_max

    @staticmethod
    def smooth_min(a, b, k: float = 10.0):
        return -torch.logsumexp(torch.stack([-k * a, -k * b]), dim=0) / k

    def forward(self, predictions, decoded_geom, x_in):
        ratio_m, ratio_v = x_in[:, 0], x_in[:, 1]
        h_b, b_fb, t_fb, t_wb = x_in[:, 3], x_in[:, 4], x_in[:, 5], x_in[:, 6]
        f_yb, f_yp = x_in[:, 13], x_in[:, 17]
        f_ub_bolt, f_vb_bolt = x_in[:, 19], x_in[:, 20]

        d = decoded_geom["d_eff"]
        t_p, b_p = decoded_geom["t_p"], decoded_geom["b_p"]
        e1, p1_mat = decoded_geom["e1"], decoded_geom["p1_matrix"]

        # 1. Solicitaciones de calculo
        W_pl_b = b_fb * t_fb * (h_b - t_fb) + t_wb * (h_b - 2 * t_fb) ** 2 / 4.0
        M_pl_Rd = (W_pl_b * f_yb) / 1.0e6                                   # kNm
        V_pl_Rd = ((h_b * t_wb) * (f_yb / (3 ** 0.5))) / 1.0e3              # kN
        M_Ed, V_Ed = ratio_m * M_pl_Rd, ratio_v * V_pl_Rd

        # 2. Capacidad (EC3)
        A_s = 0.78 * (math.pi / 4.0) * d ** 2
        F_t_Rd = (0.9 * f_ub_bolt * A_s) / 1000.0                           # kN
        m_param = (b_p / 2.0) - (t_wb / 2.0) - 0.8 * 2.0 ** 0.5 * 8.0
        l_eff = 4.0 * m_param + 1.25 * e1
        M_pl_1_Rd = (0.25 * l_eff * t_p ** 2 * f_yp) / 1000.0
        F_T_Mode1 = (4.0 * M_pl_1_Rd) / m_param
        F_T_Mode2 = (2.0 * M_pl_1_Rd + 2.0 * F_t_Rd * 30.0) / (m_param + 30.0)
        F_T_Mode3 = 2.0 * F_t_Rd
        F_row_Rd = self.smooth_min(F_T_Mode1, self.smooth_min(F_T_Mode2, F_T_Mode3))

        h_1 = h_b + decoded_geom["e_x1"] - e1
        h_2 = h_1 - p1_mat[:, 0]
        h_3 = h_2 - p1_mat[:, 1]
        M_j_Rd = (F_row_Rd * (h_1 + h_2 + h_3)) / 1000.0                    # kNm

        p_rows = F.softmax(predictions["num_rows_logits"], dim=-1)
        rows = torch.tensor(ROWS_TENSOR, device=x_in.device, dtype=torch.float32)
        n_bolts_total = 2.0 * (p_rows @ rows)
        V_j_Rd = n_bolts_total * (0.6 * f_vb_bolt * A_s) / 1000.0

        # 3. Restricciones C_k <= 0
        eta_M = M_Ed / (M_j_Rd + 1e-5)
        eta_V = V_Ed / (V_j_Rd + 1e-5)
        ratio_tp_d = t_p / d
        h_plate_total = h_b + decoded_geom["e_x1"] + decoded_geom["e_x2"]
        constraints = torch.stack([
            eta_M - 1.0,                         # C1 flexion
            eta_V - 1.0,                         # C2 cortante
            ratio_tp_d - 1.25,                   # C3 tp/d maximo
            0.5 - ratio_tp_d,                    # C4 tp/d minimo
            (h_b + 20.0) - h_plate_total,        # C5 altura de chapa
        ], dim=1)

        # 4. Objetivo primal: masa de la chapa (kg)
        masa = b_p * h_plate_total * t_p * 7.85e-6
        cost = masa.mean()

        # 5. ALM
        psi = torch.clamp(constraints, min=0.0)
        penalty = (self.lambdas * psi.mean(0) + 0.5 * self.mus * (psi ** 2).mean(0)).sum()
        total = cost + penalty
        return total, {
            "loss": total.item(), "mass": cost.item(),
            "eta_M": eta_M.mean().item(), "eta_V": eta_V.mean().item(),
            "violations": psi.mean(0).detach().cpu().numpy(),
        }

    @torch.no_grad()
    def update_multipliers(self, violations):
        """Actualizacion dual con la violacion media de la epoca (num_constraints,)."""
        v = torch.as_tensor(np.asarray(violations), dtype=torch.float32, device=self.lambdas.device)
        self.lambdas = torch.clamp(self.lambdas + self.mus * v, 0.0, self.lambda_max)
        self.mus = torch.where(v > 0.01, torch.clamp(self.mus * self.beta, max=self.mu_max), self.mus)