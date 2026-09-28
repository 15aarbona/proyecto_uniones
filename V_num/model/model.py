"""
Arquitectura v3.

Salidas:
  - drawing_code_logits, bolt_logits, slip_critical_logit   (clasificación)
  - reg_always     : g, e, d, Bp, Lp, tp                     (regresión estandarizada)
  - masked_value / masked_presence_logit : MASKED_COLUMNS = E-S, D_1..D_5, I-C, C_1..C_5,
    E-C, tws, ts, tbs, tst                                   (regresión con máscara)

p1..p12 YA NO es un target: se sustituye por E-S/D_i/I-C/C_i/E-C (geometry.py), cada una
con un único significado en todas las muestras, en vez de p_k que mezclaba roles según la
topología (D, I-C o cantonera). Al tener ya un rol fijo, una sola cabeza de regresión con
máscara (como la de los rigidizadores) es suficiente: no hace falta la clasificación sobre
rejilla ni la cabeza de "nº de pasos" de la versión anterior.

Hole, num_filas_tornillos y tiene_cantonera NO tienen cabeza: son aritmética pura sobre
las columnas anteriores (ver geometry.assemble_from_named).
"""
import torch
import torch.nn as nn

from config import CATALOGO_BOLT, MASKED_COLUMNS

N_REG_ALWAYS = 6                    # g, e, d, Bp, Lp, tp
N_MASKED = len(MASKED_COLUMNS)      # 13 geometría + 4 rigidizadores = 17


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
    def __init__(self, cat_cardinalities, num_continuous, n_drawing_codes,
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

        self.head_drawing_code = nn.Sequential(
            nn.Linear(hidden_dim, 64), nn.ReLU(), nn.Linear(64, n_drawing_codes)
        )
        self.head_bolt = nn.Sequential(
            nn.Linear(hidden_dim, 64), nn.ReLU(), nn.Linear(64, len(CATALOGO_BOLT))
        )
        self.head_slip_critical = nn.Sequential(
            nn.Linear(hidden_dim, 32), nn.ReLU(), nn.Linear(32, 1)
        )
        self.head_reg_always = nn.Sequential(
            nn.Linear(hidden_dim, 64), nn.ReLU(), nn.Linear(64, N_REG_ALWAYS)
        )
        self.head_masked_value = nn.Sequential(
            nn.Linear(hidden_dim, 128), nn.ReLU(), nn.Linear(128, N_MASKED)
        )
        self.head_masked_presence = nn.Sequential(
            nn.Linear(hidden_dim, 128), nn.ReLU(), nn.Linear(128, N_MASKED)
        )

    def forward(self, x_cat, x_num):
        emb_outs = [emb(x_cat[:, i]) for i, emb in enumerate(self.embeddings)]
        x = torch.cat(emb_outs + [x_num], dim=1)
        x = self.input_layer(x)
        for block in self.blocks:
            x = block(x)

        return {
            "drawing_code_logits": self.head_drawing_code(x),
            "bolt_logits": self.head_bolt(x),
            "slip_critical_logit": self.head_slip_critical(x).squeeze(-1),
            "reg_always": self.head_reg_always(x),
            "masked_value": self.head_masked_value(x),
            "masked_presence_logit": self.head_masked_presence(x),
        }
