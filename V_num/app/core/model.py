"""
Arquitectura v4 (mismo esqueleto ResNet que v3, cambian las cabezas).

Salidas:
  - standard_logits, bolt_logits, slip_critical_logit        (clasificación)
  - n_alma_logits, n_cantonera_logits                        (NUEVO: conteos, CE ponderada;
    describen la estructura que antes daban las columnas derivadas de los p)
  - reg_always          : g, e, d, Bp, tp, Lh                (regresión estandarizada)
  - masked_value / masked_presence_logit : MASKED_COLUMNS = P_COLUMNS (pasos p1..p12),
    tws, ts, tbs, tst                                           (regresión con máscara)
  - p_label_logits : (B, 12, N_P_LABEL_CLASSES) — clase de zona de cada paso p
    (una cabeza por p1_label..p12_label; 11 clases: BEAM_*/HAUNCH_*/AMBIGUOUS_ZONE/UNUSED)

Esquema de data/train_v3.parquet: las p activas son siempre un prefijo p1..p_k con
k = n_alma + n_cantonera + 1 (la fila 1 está en cota 'e'); las que desaparecen son
siempre las del final. La máscara de presencia se mantiene, y en post-proceso el
prefijo se fuerza con los conteos predichos (postprocess.py).

Hole, num_filas_tornillos y tiene_cantonera NO tienen cabeza: son aritmética pura
sobre Bolt y los conteos predichos.
"""
import torch
import torch.nn as nn

from .config import (
    CATALOGO_BOLT, MASKED_COLUMNS, N_ALMA_CLASSES, N_CANTONERA_CLASSES,
    P_LABEL_COLUMNS, N_P_LABEL_CLASSES,
)

N_REG_ALWAYS = 6                    # g, e, d, Bp, tp, Lh
N_MASKED = len(MASKED_COLUMNS)      # 12 p + 4 rigidizadores = 16
N_P_LABELS = len(P_LABEL_COLUMNS)   # 12 etiquetas de zona (una por paso p)


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
            nn.Linear(hidden_dim, 128), nn.ReLU(), nn.Linear(128, N_MASKED)
        )
        self.head_masked_presence = nn.Sequential(
            nn.Linear(hidden_dim, 128), nn.ReLU(), nn.Linear(128, N_MASKED)
        )
        # 12 cabezas de clasificación de zona, una por paso p (p1_label..p12_label).
        self.heads_p_label = nn.ModuleList([
            nn.Sequential(
                nn.Linear(hidden_dim, 32), nn.ReLU(),
                nn.Linear(32, N_P_LABEL_CLASSES),
            ) for _ in P_LABEL_COLUMNS
        ])

    def forward(self, x_cat, x_num):
        emb_outs = [emb(x_cat[:, i]) for i, emb in enumerate(self.embeddings)]
        x = torch.cat(emb_outs + [x_num], dim=1)
        x = self.input_layer(x)
        for block in self.blocks:
            x = block(x)

        return {
            "standard_logits": self.head_standard(x),
            "bolt_logits": self.head_bolt(x),
            "slip_critical_logit": self.head_slip_critical(x).squeeze(-1),
            "n_alma_logits": self.head_n_alma(x),
            "n_cantonera_logits": self.head_n_cantonera(x),
            "reg_always": self.head_reg_always(x),
            "masked_value": self.head_masked_value(x),
            "masked_presence_logit": self.head_masked_presence(x),
            "p_label_logits": torch.stack([head(x) for head in self.heads_p_label], dim=1),
        }
