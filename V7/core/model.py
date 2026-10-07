import torch
import torch.nn as nn
from .config import (
    CATALOGO_BOLT, N_ALMA_CLASSES, N_CANTONERA_CLASSES,
    N_P_TRANSITION_CLASSES, P_TRANSITION_UNUSED_IDX, P_TRANSITION_TO_IDX,
    REGRESSION_ALWAYS, STIFFENER_COLUMNS, N_Y, secuencia_transiciones,
)

N_REG_ALWAYS = len(REGRESSION_ALWAYS)
N_STIFFENERS = len(STIFFENER_COLUMNS)
N_MASKED = N_Y + N_STIFFENERS
TRANSITION_EMBED_DIM = 16
POSITION_EMBED_DIM = 8


def create_transition_lookup():
    lookup = torch.full((N_ALMA_CLASSES, N_CANTONERA_CLASSES, N_Y), P_TRANSITION_UNUSED_IDX, dtype=torch.long)
    for na in range(N_ALMA_CLASSES):
        for nc in range(N_CANTONERA_CLASSES):
            for pos, name in enumerate(secuencia_transiciones(na, nc)):
                lookup[na, nc, pos] = P_TRANSITION_TO_IDX[name]
    return lookup


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
    """Multitask encoder plus autoregressive GRU decoder for p1..p12."""
    def __init__(self, cat_cardinalities, num_continuous, n_standard_classes,
                 hidden_dim=192, num_blocks=3, dropout=0.1,
                 gru_hidden_dim=128):
        super().__init__()
        emb_dims = [min(16, (c + 1)//2) for c in cat_cardinalities]
        self.embeddings = nn.ModuleList([nn.Embedding(c, d) for c, d in zip(cat_cardinalities, emb_dims)])
        in_dim = sum(emb_dims) + num_continuous
        self.input_layer = nn.Sequential(nn.Linear(in_dim, hidden_dim), nn.BatchNorm1d(hidden_dim), nn.ReLU())
        self.blocks = nn.ModuleList([ResNetBlock(hidden_dim, dropout) for _ in range(num_blocks)])

        self.head_standard = nn.Sequential(nn.Linear(hidden_dim, 64), nn.ReLU(), nn.Linear(64, n_standard_classes))
        self.head_bolt = nn.Sequential(nn.Linear(hidden_dim, 64), nn.ReLU(), nn.Linear(64, len(CATALOGO_BOLT)))
        self.head_slip_critical = nn.Sequential(nn.Linear(hidden_dim, 32), nn.ReLU(), nn.Linear(32, 1))
        self.head_n_alma = nn.Sequential(nn.Linear(hidden_dim, 32), nn.ReLU(), nn.Linear(32, N_ALMA_CLASSES))
        self.head_n_cantonera = nn.Sequential(nn.Linear(hidden_dim, 32), nn.ReLU(), nn.Linear(32, N_CANTONERA_CLASSES))
        self.head_reg_always = nn.Sequential(nn.Linear(hidden_dim, 64), nn.ReLU(), nn.Linear(64, N_REG_ALWAYS))

        self.transition_embedding = nn.Embedding(N_P_TRANSITION_CLASSES, TRANSITION_EMBED_DIM)
        self.position_embedding = nn.Embedding(N_Y, POSITION_EMBED_DIM)
        # step input: global context, transition, position, previous p, cumulative p, remaining fraction
        step_dim = hidden_dim + TRANSITION_EMBED_DIM + POSITION_EMBED_DIM + 3
        self.gru_init = nn.Linear(hidden_dim, gru_hidden_dim)
        self.p_gru = nn.GRUCell(step_dim, gru_hidden_dim)
        self.p_head = nn.Sequential(nn.Linear(gru_hidden_dim, 64), nn.ReLU(), nn.Linear(64, 1))

        self.head_stiffener_value = nn.Sequential(nn.Linear(hidden_dim, 64), nn.ReLU(), nn.Linear(64, N_STIFFENERS))
        self.head_masked_presence = nn.Sequential(nn.Linear(hidden_dim, 128), nn.ReLU(), nn.Linear(128, N_MASKED))
        self.register_buffer("transition_lookup", create_transition_lookup())

    def encode(self, x_cat, x_num):
        emb = [layer(x_cat[:, i]) for i, layer in enumerate(self.embeddings)]
        x = self.input_layer(torch.cat(emb + [x_num], dim=1))
        for block in self.blocks:
            x = block(x)
        return x

    def transition_indices_from_logits(self, na_logits, nc_logits):
        return self.transition_lookup[na_logits.argmax(1), nc_logits.argmax(1)]

    def decode_p(self, context, transition_idx, p_teacher=None, p_mask=None,
                 teacher_forcing_ratio=0.0, noise_std=0.0):
        """Autoregressively predicts standardized p values."""
        batch = context.shape[0]
        hidden = torch.tanh(self.gru_init(context))
        prev_p = torch.zeros(batch, 1, device=context.device, dtype=context.dtype)
        cumulative = torch.zeros_like(prev_p)
        outputs = []
        positions = self.position_embedding(torch.arange(N_Y, device=context.device))

        for step in range(N_Y):
            trans = self.transition_embedding(transition_idx[:, step])
            pos = positions[step].unsqueeze(0).expand(batch, -1)
            remaining = torch.full_like(prev_p, (N_Y - step) / N_Y)
            step_input = torch.cat([context, trans, pos, prev_p, cumulative, remaining], dim=1)
            hidden = self.p_gru(step_input, hidden)
            p_pred = self.p_head(hidden)
            outputs.append(p_pred)

            if p_teacher is not None and teacher_forcing_ratio > 0:
                use_teacher = (torch.rand(batch, 1, device=context.device) < teacher_forcing_ratio)
                teacher_value = p_teacher[:, step:step+1]
                if noise_std > 0:
                    teacher_value = teacher_value + torch.randn_like(teacher_value) * noise_std
                next_value = torch.where(use_teacher, teacher_value, p_pred.detach())
            else:
                next_value = p_pred

            if p_mask is not None:
                active = p_mask[:, step:step+1]
                next_value = next_value * active
            prev_p = next_value
            cumulative = cumulative + next_value

        return torch.cat(outputs, dim=1)

    def forward(self, x_cat, x_num, p_transition_idx=None, p_teacher=None,
                p_mask=None, teacher_forcing_ratio=0.0, noise_std=0.0):
        x = self.encode(x_cat, x_num)
        na_logits = self.head_n_alma(x)
        nc_logits = self.head_n_cantonera(x)
        if p_transition_idx is None:
            p_transition_idx = self.transition_indices_from_logits(na_logits, nc_logits)

        p_values = self.decode_p(
            context=x, transition_idx=p_transition_idx, p_teacher=p_teacher,
            p_mask=p_mask, teacher_forcing_ratio=teacher_forcing_ratio,
            noise_std=noise_std,
        )
        stiffeners = self.head_stiffener_value(x)
        masked_value = torch.cat([p_values, stiffeners], dim=1)
        return {
            "standard_logits": self.head_standard(x),
            "bolt_logits": self.head_bolt(x),
            "slip_critical_logit": self.head_slip_critical(x).squeeze(-1),
            "n_alma_logits": na_logits,
            "n_cantonera_logits": nc_logits,
            "reg_always": self.head_reg_always(x),
            "masked_value": masked_value,
            "masked_presence_logit": self.head_masked_presence(x),
            "p_transition_idx_used": p_transition_idx,
        }
