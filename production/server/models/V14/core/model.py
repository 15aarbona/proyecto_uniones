"""Arquitectura PINN (identica a la del notebook, para cargar su state_dict)."""
import torch
import torch.nn as nn
import torch.nn.functional as F

from .config import BOLT_DIAMETERS


class ResidualBlock(nn.Module):
    def __init__(self, hidden_dim, dropout_rate=0.1):
        super().__init__()
        self.fc1 = nn.Linear(hidden_dim, hidden_dim)
        self.norm1 = nn.LayerNorm(hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.norm2 = nn.LayerNorm(hidden_dim)
        self.dropout = nn.Dropout(dropout_rate)
        self.act = nn.SiLU()

    def forward(self, x):
        r = x
        x = self.act(self.norm1(self.fc1(x)))
        x = self.dropout(x)
        x = self.norm2(self.fc2(x))
        return self.act(x + r)


class BoltedConnectionPINN(nn.Module):
    def __init__(self, input_dim=21, hidden_dim=256, num_res_blocks=3, dropout_rate=0.1):
        super().__init__()
        self.input_layer = nn.Linear(input_dim, hidden_dim)
        self.input_norm = nn.LayerNorm(hidden_dim)
        self.act = nn.SiLU()
        self.res_blocks = nn.ModuleList(
            [ResidualBlock(hidden_dim, dropout_rate) for _ in range(num_res_blocks)])
        self.head_bolt_diam = nn.Linear(hidden_dim, len(BOLT_DIAMETERS))
        self.head_num_rows = nn.Linear(hidden_dim, 5)    # filas de 2 a 6
        self.head_plate = nn.Linear(hidden_dim, 4)       # [t_p, b_p, e_x1, e_x2]
        self.head_layout = nn.Linear(hidden_dim, 6)      # alphas adimensionales

    def forward(self, x_in):
        h = self.act(self.input_norm(self.input_layer(x_in)))
        for block in self.res_blocks:
            h = block(h)
        p = self.head_plate(h)
        return {
            "bolt_diam_logits": self.head_bolt_diam(h),
            "num_rows_logits": self.head_num_rows(h),
            "plate_dims": torch.cat([
                F.softplus(p[:, 0:1]) + 8.0,      # tp >= 8
                F.softplus(p[:, 1:2]) + 120.0,    # bp >= 120
                F.softplus(p[:, 2:3]) + 30.0,     # e_x1 >= 30
                F.softplus(p[:, 3:4]) + 30.0,     # e_x2 >= 30
            ], dim=1),
            "layout_alphas": torch.sigmoid(self.head_layout(h)),
        }

    def decode_geometry(self, preds, x_in, d_eff):
        """Decodificador del notebook, pero con el diametro DISCRETO ya elegido (d_eff)
        en lugar de la media ponderada por softmax."""
        t_p, b_p, e_x1, e_x2 = preds["plate_dims"].unbind(dim=1)
        a = preds["layout_alphas"]
        t_wb = x_in[:, 6]                       # tw de la viga (indice 6 del vector de 21)
        d_0 = d_eff + 2.0
        e1_min = 1.2 * d_0
        e1 = e1_min + a[:, 0] * torch.clamp(e_x1 - e1_min, min=5.0)
        p1_min = 2.2 * d_0
        p1_mat = torch.stack([p1_min + a[:, i + 1] * 40.0 for i in range(4)], dim=1)
        e2_min = 1.2 * d_0
        e2_max = torch.clamp(b_p / 2.0 - t_wb / 2.0 - e2_min, min=10.0)
        e2 = e2_min + a[:, 5] * (e2_max - e2_min)
        return {"t_p": t_p, "b_p": b_p, "e_x1": e_x1, "e_x2": e_x2,
                "e1": e1, "p1_matrix": p1_mat, "e2": e2}