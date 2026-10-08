"""
Arquitectura v4 (encoder ResNet + cabezas por paso, con refinamiento en 2 pasadas).

Salidas:
  - standard_logits, bolt_logits, slip_critical_logit        (clasificación)
  - n_alma_logits, n_cantonera_logits                        (conteos de filas)
  - reg_always          : g, e, d, Bp, tp                   (regresión estandarizada)
  - masked_value / masked_presence_logit : MASKED_COLUMNS = p1..p12, tws, ts, tbs, tst, Lh
  - role_logits         : (B, 12, N_ROLE_CLASSES)            (rol geométrico por paso, auxiliar)

Cambios respecto a la versión por-slot:
  - P1: cada slot recibe el contexto geométrico (e, d predichos + conteos suaves).
  - P2: refinamiento en DOS PASADAS. Pasada 1 predice p^; con su suma acumulada (estado de
        posición, en espacio estandarizado) la pasada 2 refina cada p. No es secuencial
        paso a paso: usa posiciones conjuntas.
  - P3: cabeza auxiliar de rol (5 clases: TOP/BEAM_INTERIOR/BOTTOM/HAUNCH/SIN_CARTABON),
        usada también como condicionamiento del valor.
La convención: fila 1 en 'e'; p1 = fila1->fila2; nº de p activas es un prefijo (gating por
presencia en postproceso).
"""
import torch
import torch.nn as nn

from .config import (
    CATALOGO_BOLT, MASKED_COLUMNS, P_COLUMNS, STIFFENER_COLUMNS,
    N_ALMA_CLASSES, N_CANTONERA_CLASSES, N_ROLE_CLASSES, REGRESSION_ALWAYS,
)

N_REG_ALWAYS = len(REGRESSION_ALWAYS)        # g, e, d, Bp, tp
N_P = len(P_COLUMNS)                         # 12 pasos p (cabezas por-slot)
N_OTHER_MASKED = len(STIFFENER_COLUMNS) + 1  # tws, ts, tbs, tst, Lh = 5
N_MASKED = N_P + N_OTHER_MASKED              # 17 (orden MASKED_COLUMNS)


class ResNetBlock(nn.Module):
    def __init__(self, dim, dropout=0.1):
        super().__init__()
        self.fc1 = nn.Linear(dim, dim)
        self.bn1 = nn.BatchNorm1d(dim)
        self.fc2 = nn.Linear(dim, dim)
        self.bn2 = nn.BatchNorm1d(dim)
        self.dropout = nn.Dropout(dropout)
        self.act = nn.ReLU()

    def forward(self, x):
        residual = x
        out = self.act(self.bn1(self.fc1(x)))
        out = self.dropout(out)
        out = self.bn2(self.fc2(out))
        return self.act(out + residual)


class ConnectionDesignNet(nn.Module):
    def __init__(self, cat_cardinalities, num_continuous, n_standard_classes,
                 hidden_dim=192, num_blocks=3, dropout=0.1):
        super().__init__()
        self.embeddings = nn.ModuleList([
            nn.Embedding(card, min(16, (card + 1) // 2)) for card in cat_cardinalities
        ])
        emb_dim = sum(min(16, (c + 1) // 2) for c in cat_cardinalities)
        in_dim = emb_dim + num_continuous

        self.input_layer = nn.Sequential(
            nn.Linear(in_dim, hidden_dim), nn.BatchNorm1d(hidden_dim), nn.ReLU()
        )
        self.blocks = nn.ModuleList([ResNetBlock(hidden_dim, dropout) for _ in range(num_blocks)])

        self.head_standard = nn.Sequential(
            nn.Linear(hidden_dim, 64), nn.ReLU(), nn.Linear(64, n_standard_classes)
        )
        self.head_bolt = nn.Sequential(
            nn.Linear(hidden_dim, 64), nn.ReLU(), nn.Linear(64, len(CATALOGO_BOLT))
        )
        self.head_slip_critical = nn.Sequential(
            nn.Linear(hidden_dim, 32), nn.ReLU(), nn.Linear(32, 1)
        )
        self.head_n_alma = nn.Sequential(
            nn.Linear(hidden_dim, 32), nn.ReLU(), nn.Linear(32, N_ALMA_CLASSES)
        )
        self.head_n_cantonera = nn.Sequential(
            nn.Linear(hidden_dim, 32), nn.ReLU(), nn.Linear(32, N_CANTONERA_CLASSES)
        )
        self.head_reg_always = nn.Sequential(
            nn.Linear(hidden_dim, 64), nn.ReLU(), nn.Linear(64, N_REG_ALWAYS)
        )
        self.head_masked_value = nn.Sequential(
            nn.Linear(hidden_dim, 64), nn.ReLU(), nn.Linear(64, N_OTHER_MASKED)
        )
        self.head_masked_presence = nn.Sequential(
            nn.Linear(hidden_dim, 64), nn.ReLU(), nn.Linear(64, N_OTHER_MASKED)
        )

        # --- Condicionamiento por slot, conteos suaves y geometría (P1) ---
        self.E_slot = nn.Embedding(N_P, hidden_dim)
        self.E_na = nn.Embedding(N_ALMA_CLASSES, hidden_dim)
        self.E_nc = nn.Embedding(N_CANTONERA_CLASSES, hidden_dim)
        self.geom_proj = nn.Linear(2, hidden_dim)     # (e, d) predichos
        # --- Rol (P3): embedding + cabeza auxiliar por slot ---
        self.E_role = nn.Embedding(N_ROLE_CLASSES, hidden_dim)
        self.head_p_role = nn.ModuleList([
            nn.Sequential(nn.Linear(hidden_dim, 32), nn.ReLU(), nn.Linear(32, N_ROLE_CLASSES))
            for _ in range(N_P)
        ])
        # --- Pasada 1: valor + presencia por slot ---
        self.head_p_value = nn.ModuleList([
            nn.Sequential(nn.Linear(hidden_dim, 64), nn.ReLU(), nn.Linear(64, 1))
            for _ in range(N_P)
        ])
        self.head_p_presence = nn.ModuleList([
            nn.Sequential(nn.Linear(hidden_dim, 32), nn.ReLU(), nn.Linear(32, 1))
            for _ in range(N_P)
        ])
        # --- Pasada 2 (P2): estado de posición -> refinamiento del valor ---
        self.state_proj = nn.Linear(2, hidden_dim)    # (Y_{j-1}, Y_j) estandarizados
        self.head_p_value2 = nn.ModuleList([
            nn.Sequential(nn.Linear(hidden_dim, 64), nn.ReLU(), nn.Linear(64, 1))
            for _ in range(N_P)
        ])
        for emb in (self.E_slot, self.E_na, self.E_nc, self.E_role):
            nn.init.zeros_(emb.weight)
        nn.init.zeros_(self.geom_proj.weight); nn.init.zeros_(self.geom_proj.bias)
        nn.init.zeros_(self.state_proj.weight); nn.init.zeros_(self.state_proj.bias)

    def forward(self, x_cat, x_num):
        emb_outs = [emb(x_cat[:, i]) for i, emb in enumerate(self.embeddings)]
        x = torch.cat(emb_outs + [x_num], dim=1)
        x = self.input_layer(x)
        for block in self.blocks:
            x = block(x)

        reg = self.head_reg_always(x)                       # (B, N_REG_ALWAYS)
        e_std = reg[:, 1:2]
        d_std = reg[:, 2:3]
        n_alma_logits = self.head_n_alma(x)
        n_cantonera_logits = self.head_n_cantonera(x)

        # Conteos suaves + geometría como contexto (P1)
        c_na = torch.softmax(n_alma_logits, dim=1)
        c_nc = torch.softmax(n_cantonera_logits, dim=1)
        count_emb = c_na @ self.E_na.weight + c_nc @ self.E_nc.weight     # (B, H)
        geom_emb = self.geom_proj(torch.cat([e_std, d_std], dim=1))       # (B, H)

        slot_emb = self.E_slot.weight.unsqueeze(0)                        # (1, N_P, H)
        h_base = x.unsqueeze(1) + slot_emb + count_emb.unsqueeze(1) + geom_emb.unsqueeze(1)

        # Rol por paso (P3): predicho y usado como condicionamiento
        role_logits = torch.stack([self.head_p_role[k](h_base[:, k]) for k in range(N_P)], dim=1)  # (B,N_P,C)
        role_idx = role_logits.argmax(dim=-1)
        h1 = h_base + self.E_role(role_idx)

        # Pasada 1
        p1 = torch.cat([self.head_p_value[k](h1[:, k]) for k in range(N_P)], dim=1)      # (B, N_P)
        p_pres = torch.cat([self.head_p_presence[k](h1[:, k]) for k in range(N_P)], dim=1)

        # Estado de posición acumulada (P2) y refinamiento
        cum = torch.cumsum(p1, dim=1)
        prev = cum - p1
        state = torch.stack([prev, cum], dim=-1)                          # (B, N_P, 2)
        h2 = h1 + self.state_proj(state)
        p2 = torch.cat([self.head_p_value2[k](h2[:, k]) for k in range(N_P)], dim=1)     # (B, N_P)

        other_val = self.head_masked_value(x)
        other_pres = self.head_masked_presence(x)

        return {
            "standard_logits": self.head_standard(x),
            "bolt_logits": self.head_bolt(x),
            "slip_critical_logit": self.head_slip_critical(x).squeeze(-1),
            "n_alma_logits": n_alma_logits,
            "n_cantonera_logits": n_cantonera_logits,
            "reg_always": reg,
            "masked_value": torch.cat([p2, other_val], dim=1),            # (B, N_MASKED)
            "masked_presence_logit": torch.cat([p_pres, other_pres], dim=1),
            "role_logits": role_logits,                                   # (B, N_P, N_ROLE_CLASSES)
        }
