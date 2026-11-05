"""Modelo multitarea con decodificador GRU autorregresivo para p1...p12.

Ablacion v3:
- El valor anterior se entrega a la GRU en milimetros normalizados.
- La suma acumulada se normaliza con una escala fija, no con BEAM_d_mm.
- No se introduce ruido por defecto durante el entrenamiento.
- Se mantiene la topologia por transiciones.
"""

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from .config import (
    CATALOGO_BOLT,
    N_ALMA_CLASSES,
    N_VIGA_CLASSES,
    N_CANTONERA_CLASSES,
    N_ROWS_CLASSES,
    N_P_VIGA,
    N_P_CANTONERA,
    MIN_ROW_GAP_MM,
    N_P_TRANSITION_CLASSES,
    P_TRANSITION_UNUSED_IDX,
    P_TRANSITION_TO_IDX,
    REGRESSION_ALWAYS,
    STIFFENER_COLUMNS,
    N_Y,
    secuencia_transiciones,
)

N_REG_ALWAYS = len(REGRESSION_ALWAYS)
N_STIFFENERS = len(STIFFENER_COLUMNS)
N_MASKED = N_Y + N_STIFFENERS
TRANSITION_EMBED_DIM = 16
POSITION_EMBED_DIM = 8


def create_transition_lookup():
    lookup = torch.full(
        (N_ALMA_CLASSES, N_CANTONERA_CLASSES, N_Y),
        P_TRANSITION_UNUSED_IDX,
        dtype=torch.long,
    )
    for n_alma in range(N_ALMA_CLASSES):
        for n_cantonera in range(N_CANTONERA_CLASSES):
            transitions = secuencia_transiciones(n_alma, n_cantonera)
            if len(transitions) > N_Y:
                raise ValueError("La topologia excede el numero maximo de p.")
            for position, transition in enumerate(transitions):
                lookup[n_alma, n_cantonera, position] = P_TRANSITION_TO_IDX[transition]
    return lookup


class ResNetBlock(nn.Module):
    def __init__(self, dim, dropout=0.1):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(dim, dim),
            nn.BatchNorm1d(dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(dim, dim),
            nn.BatchNorm1d(dim),
        )
        self.activation = nn.ReLU()

    def forward(self, x):
        return self.activation(x + self.network(x))


class ConnectionDesignNet(nn.Module):
    def __init__(
        self,
        cat_cardinalities,
        num_continuous,
        n_standard_classes,
        p_mean_mm,
        p_std_mm,
        hidden_dim=192,
        num_blocks=3,
        dropout=0.1,
        gru_hidden_dim=128,
        previous_p_scale_mm=200.0,
        cumulative_scale_mm=1000.0,
    ):
        super().__init__()

        self.previous_p_scale_mm = float(previous_p_scale_mm)
        self.cumulative_scale_mm = float(cumulative_scale_mm)

        embedding_dims = [
            min(16, (cardinality + 1) // 2)
            for cardinality in cat_cardinalities
        ]
        self.embeddings = nn.ModuleList(
            [
                nn.Embedding(cardinality, embedding_dim)
                for cardinality, embedding_dim in zip(
                    cat_cardinalities,
                    embedding_dims,
                )
            ]
        )

        input_dim = sum(embedding_dims) + num_continuous
        self.input_layer = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
        )
        self.blocks = nn.ModuleList(
            [ResNetBlock(hidden_dim, dropout) for _ in range(num_blocks)]
        )

        def classification_head(n_outputs, intermediate=64):
            return nn.Sequential(
                nn.Linear(hidden_dim, intermediate),
                nn.ReLU(),
                nn.Linear(intermediate, n_outputs),
            )

        self.head_standard = classification_head(n_standard_classes)
        self.head_bolt = classification_head(len(CATALOGO_BOLT))
        self.head_slip_critical = classification_head(1, intermediate=32)
        self.head_n_alma = classification_head(N_ALMA_CLASSES, intermediate=32)
        self.head_n_cantonera = classification_head(
            N_CANTONERA_CLASSES,
            intermediate=32,
        )
        self.head_reg_always = classification_head(N_REG_ALWAYS)
        self.head_stiffener_value = classification_head(N_STIFFENERS)
        self.head_masked_presence = classification_head(N_MASKED, intermediate=128)

        self.transition_embedding = nn.Embedding(
            N_P_TRANSITION_CLASSES,
            TRANSITION_EMBED_DIM,
        )
        self.position_embedding = nn.Embedding(N_Y, POSITION_EMBED_DIM)

        # Contexto global + transicion + posicion + p previa + acumulado + restante + activo.
        gru_input_dim = (
            hidden_dim
            + TRANSITION_EMBED_DIM
            + POSITION_EMBED_DIM
            + 4
        )
        self.gru_initial_state = nn.Linear(hidden_dim, gru_hidden_dim)
        self.p_gru = nn.GRUCell(gru_input_dim, gru_hidden_dim)
        self.p_head = nn.Sequential(
            nn.Linear(gru_hidden_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

        self.register_buffer("transition_lookup", create_transition_lookup())
        self.register_buffer(
            "p_mean_mm",
            torch.as_tensor(p_mean_mm, dtype=torch.float32).view(1, N_Y),
        )
        self.register_buffer(
            "p_std_mm",
            torch.as_tensor(p_std_mm, dtype=torch.float32).view(1, N_Y),
        )

    def encode(self, x_cat, x_num):
        embedded = [
            embedding(x_cat[:, index])
            for index, embedding in enumerate(self.embeddings)
        ]
        x = self.input_layer(torch.cat(embedded + [x_num], dim=1))
        for block in self.blocks:
            x = block(x)
        return x

    def transitions_from_logits(self, n_alma_logits, n_cantonera_logits):
        n_alma = n_alma_logits.argmax(dim=1)
        n_cantonera = n_cantonera_logits.argmax(dim=1)
        return self.transition_lookup[n_alma, n_cantonera]

    def decode_p(
        self,
        context,
        transitions,
        active_count,
        p_teacher=None,
        teacher_forcing_ratio=0.0,
    ):
        batch_size = context.shape[0]
        hidden = torch.tanh(self.gru_initial_state(context))
        previous_p_mm = torch.zeros(
            batch_size,
            1,
            device=context.device,
            dtype=context.dtype,
        )
        cumulative_mm = torch.zeros_like(previous_p_mm)
        active_count = active_count.view(-1, 1).clamp_min(1)
        position_embeddings = self.position_embedding(
            torch.arange(N_Y, device=context.device)
        )

        predictions = []

        for step in range(N_Y):
            transition_embedding = self.transition_embedding(
                transitions[:, step]
            )
            position_embedding = position_embeddings[step].unsqueeze(0).expand(
                batch_size,
                -1,
            )
            remaining_fraction = (
                (active_count - step).clamp_min(0) / active_count
            ).float()
            active = (step < active_count).float()

            step_input = torch.cat(
                [
                    context,
                    transition_embedding,
                    position_embedding,
                    previous_p_mm / self.previous_p_scale_mm,
                    cumulative_mm / self.cumulative_scale_mm,
                    remaining_fraction,
                    active,
                ],
                dim=1,
            )

            hidden = self.p_gru(step_input, hidden)
            predicted_standard = self.p_head(hidden)
            predictions.append(predicted_standard)

            predicted_mm = (
                predicted_standard * self.p_std_mm[:, step : step + 1]
                + self.p_mean_mm[:, step : step + 1]
            )

            if p_teacher is not None and teacher_forcing_ratio > 0.0:
                teacher_mm = (
                    p_teacher[:, step : step + 1]
                    * self.p_std_mm[:, step : step + 1]
                    + self.p_mean_mm[:, step : step + 1]
                )
                use_teacher = (
                    torch.rand(batch_size, 1, device=context.device)
                    < teacher_forcing_ratio
                )
                next_p_mm = torch.where(
                    use_teacher,
                    teacher_mm,
                    predicted_mm.detach(),
                )
            else:
                next_p_mm = predicted_mm

            previous_p_mm = next_p_mm * active
            cumulative_mm = cumulative_mm + previous_p_mm

        return torch.cat(predictions, dim=1)

    def forward(
        self,
        x_cat,
        x_num,
        p_transition_idx=None,
        p_teacher=None,
        active_count=None,
        teacher_forcing_ratio=0.0,
    ):
        context = self.encode(x_cat, x_num)

        n_alma_logits = self.head_n_alma(context)
        n_cantonera_logits = self.head_n_cantonera(context)

        if p_transition_idx is None:
            p_transition_idx = self.transitions_from_logits(
                n_alma_logits,
                n_cantonera_logits,
            )

        if active_count is None:
            active_count = (
                n_alma_logits.argmax(dim=1)
                + n_cantonera_logits.argmax(dim=1)
                + 1
            )

        p_values = self.decode_p(
            context=context,
            transitions=p_transition_idx,
            active_count=active_count,
            p_teacher=p_teacher,
            teacher_forcing_ratio=teacher_forcing_ratio,
        )
        stiffener_values = self.head_stiffener_value(context)

        return {
            "standard_logits": self.head_standard(context),
            "bolt_logits": self.head_bolt(context),
            "slip_critical_logit": self.head_slip_critical(context).squeeze(-1),
            "n_alma_logits": n_alma_logits,
            "n_cantonera_logits": n_cantonera_logits,
            "reg_always": self.head_reg_always(context),
            "masked_value": torch.cat(
                [p_values, stiffener_values],
                dim=1,
            ),
            "masked_presence_logit": self.head_masked_presence(context),
            "p_transition_idx_used": p_transition_idx,
        }


# =============================================================================
# V4: cabeza de p DISCRETIZADA (rejilla de 5 mm) + topologia conjunta opcional
# =============================================================================
#
# Por que:
#   * Las p viven en una rejilla de 5 mm y su distribucion condicionada es
#     multimodal. Una regresion con Huber (beta=1 en z-score ~ MSE) predice la
#     MEDIA entre modos -> colas pesadas. La metrica (<=10 mm) premia el MODO.
#   * La topologia (n_alma, n_cantonera) es una decision conjunta; dos cabezas
#     independientes ignoran su correlacion. Con joint_topology=True se usa una
#     unica softmax sobre las combinaciones.
#
# Compatibilidad: mismas claves de salida que v3 (+ "p_logits" y, si
# joint_topology, "topology_logits"). "masked_value"[:, :N_Y] sigue siendo el
# valor (moda) en z-score, asi que predict_loader / decode_outputs / metricas
# funcionan sin cambios.


def n_bins_from_train(df_train, p_columns, step_mm=5.0, margin_bins=4):
    """Numero de bins: cubre el p maximo observado en train + margen."""
    p_max = float(df_train[p_columns].fillna(0).to_numpy().max())
    return int(round(p_max / step_mm)) + 1 + margin_bins


class ConnectionDesignNetV4(ConnectionDesignNet):
    def __init__(
        self,
        *args,
        n_p_bins,
        p_bin_step_mm=5.0,
        joint_topology=False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.n_p_bins = int(n_p_bins)
        self.p_bin_step_mm = float(p_bin_step_mm)
        self.joint_topology = bool(joint_topology)

        hidden_dim = self.input_layer[0].out_features
        gru_hidden = self.p_gru.hidden_size

        # Sustituye la cabeza de regresion de v3 por una de clasificacion.
        self.p_head = nn.Sequential(
            nn.Linear(gru_hidden, 128),
            nn.ReLU(),
            nn.Linear(128, self.n_p_bins),
        )
        self.register_buffer(
            "p_bin_values_mm",
            torch.arange(self.n_p_bins, dtype=torch.float32) * self.p_bin_step_mm,
        )
        # El bin 0 (0 mm) no es una separacion valida cuando la fila esta activa.
        bin_mask = torch.zeros(self.n_p_bins)
        bin_mask[0] = -1e4
        self.register_buffer("p_bin_mask", bin_mask)

        if self.joint_topology:
            self.head_topology = nn.Sequential(
                nn.Linear(hidden_dim, 64),
                nn.ReLU(),
                nn.Linear(64, N_ALMA_CLASSES * N_CANTONERA_CLASSES),
            )

    def topology_heads(self, context):
        """Devuelve (n_alma_logits, n_cantonera_logits, topology_logits|None).

        En modo conjunto, los logits marginales son las rebanadas de la matriz
        conjunta que pasan por el maximo (a*, c*): asi argmax(n_alma_logits)=a*
        y argmax(n_cantonera_logits)=c*, consistentes con la decision conjunta.
        """
        if not self.joint_topology:
            return self.head_n_alma(context), self.head_n_cantonera(context), None
        topology_logits = self.head_topology(context)
        grid = topology_logits.view(-1, N_ALMA_CLASSES, N_CANTONERA_CLASSES)
        best = topology_logits.argmax(dim=1)
        a_star = best // N_CANTONERA_CLASSES
        c_star = best % N_CANTONERA_CLASSES
        rows = torch.arange(grid.shape[0], device=grid.device)
        n_alma_logits = grid[rows, :, c_star]
        n_cantonera_logits = grid[rows, a_star, :]
        return n_alma_logits, n_cantonera_logits, topology_logits

    def decode_p(
        self,
        context,
        transitions,
        active_count,
        p_teacher=None,
        teacher_forcing_ratio=0.0,
    ):
        """Devuelve logits (B, N_Y, n_bins). La realimentacion usa la MODA."""
        batch_size = context.shape[0]
        hidden = torch.tanh(self.gru_initial_state(context))
        previous_p_mm = torch.zeros(batch_size, 1, device=context.device, dtype=context.dtype)
        cumulative_mm = torch.zeros_like(previous_p_mm)
        active_count = active_count.view(-1, 1).clamp_min(1)
        position_embeddings = self.position_embedding(
            torch.arange(N_Y, device=context.device)
        )

        all_logits = []
        for step in range(N_Y):
            transition_embedding = self.transition_embedding(transitions[:, step])
            position_embedding = position_embeddings[step].unsqueeze(0).expand(batch_size, -1)
            remaining_fraction = ((active_count - step).clamp_min(0) / active_count).float()
            active = (step < active_count).float()

            step_input = torch.cat(
                [
                    context,
                    transition_embedding,
                    position_embedding,
                    previous_p_mm / self.previous_p_scale_mm,
                    cumulative_mm / self.cumulative_scale_mm,
                    remaining_fraction,
                    active,
                ],
                dim=1,
            )
            hidden = self.p_gru(step_input, hidden)
            logits = self.p_head(hidden) + self.p_bin_mask
            all_logits.append(logits)

            # Valor realimentado: moda de la distribucion (ya en la rejilla de 5 mm).
            predicted_mm = self.p_bin_values_mm[logits.argmax(dim=1)].unsqueeze(1).detach()

            if p_teacher is not None and teacher_forcing_ratio > 0.0:
                teacher_mm = (
                    p_teacher[:, step : step + 1] * self.p_std_mm[:, step : step + 1]
                    + self.p_mean_mm[:, step : step + 1]
                )
                use_teacher = (
                    torch.rand(batch_size, 1, device=context.device) < teacher_forcing_ratio
                )
                next_p_mm = torch.where(use_teacher, teacher_mm, predicted_mm)
            else:
                next_p_mm = predicted_mm

            previous_p_mm = next_p_mm * active
            cumulative_mm = cumulative_mm + previous_p_mm

        return torch.stack(all_logits, dim=1)

    def forward(
        self,
        x_cat,
        x_num,
        p_transition_idx=None,
        p_teacher=None,
        active_count=None,
        teacher_forcing_ratio=0.0,
    ):
        context = self.encode(x_cat, x_num)

        n_alma_logits, n_cantonera_logits, topology_logits = self.topology_heads(context)

        if p_transition_idx is None:
            p_transition_idx = self.transitions_from_logits(n_alma_logits, n_cantonera_logits)
        if active_count is None:
            active_count = n_alma_logits.argmax(dim=1) + n_cantonera_logits.argmax(dim=1) + 1

        p_logits = self.decode_p(
            context=context,
            transitions=p_transition_idx,
            active_count=active_count,
            p_teacher=p_teacher,
            teacher_forcing_ratio=teacher_forcing_ratio,
        )

        # Moda -> mm -> z-score (compatible con el resto del pipeline).
        p_mode_mm = self.p_bin_values_mm[p_logits.argmax(dim=-1)]
        p_values_z = (p_mode_mm - self.p_mean_mm) / self.p_std_mm
        stiffener_values = self.head_stiffener_value(context)

        outputs = {
            "standard_logits": self.head_standard(context),
            "bolt_logits": self.head_bolt(context),
            "slip_critical_logit": self.head_slip_critical(context).squeeze(-1),
            "n_alma_logits": n_alma_logits,
            "n_cantonera_logits": n_cantonera_logits,
            "reg_always": self.head_reg_always(context),
            "masked_value": torch.cat([p_values_z, stiffener_values], dim=1),
            "masked_presence_logit": self.head_masked_presence(context),
            "p_transition_idx_used": p_transition_idx,
            "p_logits": p_logits,
        }
        if topology_logits is not None:
            outputs["topology_logits"] = topology_logits
        return outputs


class ConnectionDesignNetZones(ConnectionDesignNet):
    """p separadas en viga y cantonera, con restricciones de zona.

    - n_viga y n_cantonera se predicen con clasificacion.
    - p_viga y p_cantonera se decodifican con dos GRU separadas.
    - bottom_margin se predice one-shot y es siempre positiva.
    - Las distancias se enmascaran con la geometria para no salir de su zona.
    """

    def __init__(
        self,
        *args,
        n_p_bins,
        p_bin_step_mm=5.0,
        reg_mean_mm=None,
        reg_std_mm=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.n_p_bins = int(n_p_bins)
        self.p_bin_step_mm = float(p_bin_step_mm)

        gru_hidden = self.p_gru.hidden_size
        del self.head_n_alma
        del self.p_gru
        del self.p_head

        hidden_dim = self.input_layer[0].out_features
        self.head_n_viga = nn.Sequential(
            nn.Linear(hidden_dim, 32),
            nn.ReLU(),
            nn.Linear(32, N_VIGA_CLASSES),
        )
        self.head_bottom_margin = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )
        self.viga_gru = nn.GRUCell(
            hidden_dim + POSITION_EMBED_DIM + 4,
            gru_hidden,
        )
        self.viga_head = nn.Sequential(
            nn.Linear(gru_hidden, 128),
            nn.ReLU(),
            nn.Linear(128, self.n_p_bins),
        )
        self.cantonera_gru = nn.GRUCell(
            hidden_dim + POSITION_EMBED_DIM + 6,
            gru_hidden,
        )
        self.cantonera_head = nn.Sequential(
            nn.Linear(gru_hidden, 128),
            nn.ReLU(),
            nn.Linear(128, self.n_p_bins),
        )
        self.register_buffer(
            "p_bin_values_mm",
            torch.arange(self.n_p_bins, dtype=torch.float32) * self.p_bin_step_mm,
        )
        bin_mask = torch.zeros(self.n_p_bins)
        bin_mask[0] = -1e4
        self.register_buffer("p_bin_mask", bin_mask)
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

    def _zone_logits(
        self,
        head,
        gru,
        context,
        hidden,
        active_count,
        current_y,
        zone_min,
        zone_max,
        n_steps,
        first_min,
        teacher=None,
        teacher_forcing_ratio=0.0,
        extra=None,
        apply_zone_masks=True,
    ):
        batch_size = context.shape[0]
        active_count = active_count.view(-1, 1)
        previous_p = torch.zeros(batch_size, 1, device=context.device, dtype=context.dtype)
        cumulative = torch.zeros_like(previous_p)
        positions = self.position_embedding(torch.arange(n_steps, device=context.device))
        all_logits = []
        values = []

        for step in range(n_steps):
            position = positions[step].unsqueeze(0).expand(batch_size, -1)
            remaining_fraction = (
                (active_count - step).clamp_min(0) / active_count.clamp_min(1)
            ).float()
            active = (step < active_count).float()
            parts = [
                context,
                position,
                previous_p / self.previous_p_scale_mm,
                cumulative / self.cumulative_scale_mm,
                remaining_fraction,
                active,
            ]
            if extra is not None:
                parts.append(extra)
            hidden = gru(torch.cat(parts, dim=1), hidden)
            logits = head(hidden) + self.p_bin_mask

            # Solo bins que mantienen la fila dentro de la zona y dejan sitio
            # para las filas restantes.
            remaining_rows = (active_count - step - 1).clamp_min(0).view(-1, 1)
            candidate_y = current_y + self.p_bin_values_mm.view(1, -1)
            max_y = zone_max - remaining_rows * MIN_ROW_GAP_MM
            min_y = torch.where(
                torch.full_like(active_count.view(-1, 1), step == 0, dtype=torch.bool),
                first_min,
                current_y + MIN_ROW_GAP_MM,
            )
            if apply_zone_masks:
                allowed = (candidate_y >= min_y) & (candidate_y <= max_y)
                # Si la mascara no deja ningun bin, no se fuerza una fila invalida.
                has_option = allowed.any(dim=1, keepdim=True)
                allowed = torch.where(has_option, allowed, torch.ones_like(allowed))
                logits = logits.masked_fill(~allowed, -1e4)
            all_logits.append(logits)

            predicted = self.p_bin_values_mm[logits.argmax(dim=1)].view(-1, 1)
            predicted = predicted * active
            if teacher is not None and teacher_forcing_ratio > 0.0:
                teacher_value = teacher[:, step : step + 1] * active
                use_teacher = (
                    torch.rand(batch_size, 1, device=context.device)
                    < teacher_forcing_ratio
                )
                next_p = torch.where(use_teacher, teacher_value, predicted.detach())
            else:
                next_p = predicted.detach()
            values.append(predicted)
            previous_p = next_p
            cumulative = cumulative + next_p * active
            current_y = current_y + next_p * active

        return (
            torch.stack(all_logits, dim=1),
            torch.cat(values, dim=1),
            hidden,
            current_y,
            cumulative,
        )

    def forward(
        self,
        x_cat,
        x_num,
        p_transition_idx=None,
        p_teacher=None,
        active_count=None,
        teacher_forcing_ratio=0.0,
        beam_d_mm=None,
        beam_tf_mm=None,
        p_viga_teacher=None,
        p_cantonera_teacher=None,
        e_teacher=None,
        d_teacher=None,
        n_viga_teacher=None,
        n_cantonera_teacher=None,
        apply_zone_masks=False,
    ):
        context = self.encode(x_cat, x_num)
        n_viga_logits = self.head_n_viga(context)
        n_cantonera_logits = self.head_n_cantonera(context)
        if active_count is None:
            active_count = n_viga_logits.argmax(dim=1) + n_cantonera_logits.argmax(dim=1) + 1
        n_viga = n_viga_logits.argmax(dim=1)
        n_cantonera = n_cantonera_logits.argmax(dim=1)
        n_viga_decode = n_viga if n_viga_teacher is None else n_viga_teacher
        n_cantonera_decode = (
            n_cantonera if n_cantonera_teacher is None else n_cantonera_teacher
        )

        reg = self.head_reg_always(context) * self.reg_std_mm + self.reg_mean_mm
        e = reg[:, REGRESSION_ALWAYS.index("e") : REGRESSION_ALWAYS.index("e") + 1]
        d = reg[:, REGRESSION_ALWAYS.index("d") : REGRESSION_ALWAYS.index("d") + 1]
        if e_teacher is not None:
            e_mask = e_teacher.view(-1, 1).to(device=context.device, dtype=context.dtype)
        else:
            e_mask = e
        if d_teacher is not None:
            d_mask = d_teacher.view(-1, 1).to(device=context.device, dtype=context.dtype)
        else:
            d_mask = d

        if beam_d_mm is None:
            beam_d = torch.full_like(e, 1.0)
            beam_tf = torch.zeros_like(e)
        else:
            beam_d = beam_d_mm.view(-1, 1).to(device=context.device, dtype=context.dtype)
            if beam_tf_mm is None:
                beam_tf = torch.zeros_like(e)
            else:
                beam_tf = beam_tf_mm.view(-1, 1).to(
                    device=context.device, dtype=context.dtype
                )
        top_out = e_mask + d_mask
        top_in = top_out + beam_tf
        bot_out = top_out + beam_d
        bot_in = bot_out - beam_tf
        sin60 = torch.tensor(np.sin(np.radians(60.0)), device=context.device, dtype=context.dtype)
        lh = torch.where(
            n_cantonera_decode.view(-1, 1) > 0,
            0.7 * beam_d / sin60,
            torch.zeros_like(beam_d),
        )
        angle_bottom = bot_out + lh

        viga_hidden = torch.tanh(self.gru_initial_state(context))
        viga_logits, p_viga, viga_hidden, last_viga_y, last_viga_p = self._zone_logits(
            head=self.viga_head,
            gru=self.viga_gru,
            context=context,
            hidden=viga_hidden,
            active_count=n_viga_decode,
            current_y=e_mask,
            zone_min=top_in,
            zone_max=bot_in,
            n_steps=N_P_VIGA,
            first_min=top_in,
            teacher=p_viga_teacher,
            teacher_forcing_ratio=teacher_forcing_ratio,
            apply_zone_masks=apply_zone_masks,
        )

        handoff = torch.cat(
            [last_viga_y / self.cumulative_scale_mm, last_viga_p / self.previous_p_scale_mm],
            dim=1,
        )
        cant_hidden = torch.tanh(self.gru_initial_state(context))
        cant_logits, p_cantonera, _, _, _ = self._zone_logits(
            head=self.cantonera_head,
            gru=self.cantonera_gru,
            context=context,
            hidden=cant_hidden,
            active_count=n_cantonera_decode,
            current_y=last_viga_y,
            zone_min=bot_out,
            zone_max=angle_bottom,
            n_steps=N_P_CANTONERA,
            first_min=bot_out + MIN_ROW_GAP_MM,
            teacher=p_cantonera_teacher,
            teacher_forcing_ratio=teacher_forcing_ratio,
            extra=handoff,
            apply_zone_masks=apply_zone_masks,
        )

        bottom_margin = F.softplus(self.head_bottom_margin(context))
        stiffener_values = self.head_stiffener_value(context)
        return {
            "standard_logits": self.head_standard(context),
            "bolt_logits": self.head_bolt(context),
            "slip_critical_logit": self.head_slip_critical(context).squeeze(-1),
            "n_viga_logits": n_viga_logits,
            "n_alma_logits": n_viga_logits,
            "n_cantonera_logits": n_cantonera_logits,
            "p_viga_logits": viga_logits,
            "p_cantonera_logits": cant_logits,
            "p_viga_mm": p_viga,
            "p_cantonera_mm": p_cantonera,
            "bottom_margin_mm": bottom_margin,
            "reg_always": self.head_reg_always(context),
            "masked_value": torch.cat(
                [torch.zeros(context.shape[0], N_Y, device=context.device), stiffener_values],
                dim=1,
            ),
            "masked_presence_logit": self.head_masked_presence(context),
        }


@torch.no_grad()
def p_confidence(p_logits):
    """Confianza por separacion a partir de los logits (N, N_Y, K).

    Devuelve (prob_moda, prob_dentro_10mm), ambos (N, N_Y) como numpy.
    prob_dentro_10mm = masa de probabilidad a <= 2 bins (10 mm) de la moda.
    """
    probs = torch.softmax(torch.as_tensor(p_logits), dim=-1)
    mode = probs.argmax(dim=-1, keepdim=True)
    p_mode = probs.max(dim=-1).values
    idx = torch.arange(probs.shape[-1]).view(1, 1, -1)
    near = ((idx - mode).abs() <= 2).float()
    return p_mode.numpy(), (probs * near).sum(dim=-1).numpy()



class ConnectionDesignNetV14(ConnectionDesignNet):
    """V14: p autorregresiva sin cabezas de n_alma/n_cantonera.

    La longitud de la secuencia se predice con una unica cabeza ``n_rows``
    (filas totales). Los conteos de alma y cantonera se derivan despues a partir
    de las distancias p y de la geometria de la viga.
    """

    def __init__(
        self,
        *args,
        n_p_bins,
        p_bin_step_mm=5.0,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.n_p_bins = int(n_p_bins)
        self.p_bin_step_mm = float(p_bin_step_mm)

        del self.head_n_alma
        del self.head_n_cantonera

        hidden_dim = self.input_layer[0].out_features
        gru_hidden = self.p_gru.hidden_size
        self.head_n_rows = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Linear(64, N_ROWS_CLASSES),
        )
        # Sin transiciones: contexto global + posicion + p previa + acumulado
        # + restante + activo.
        self.p_gru = nn.GRUCell(
            hidden_dim + POSITION_EMBED_DIM + 4,
            gru_hidden,
        )
        self.p_head = nn.Sequential(
            nn.Linear(gru_hidden, 128),
            nn.ReLU(),
            nn.Linear(128, self.n_p_bins),
        )
        self.register_buffer(
            "p_bin_values_mm",
            torch.arange(self.n_p_bins, dtype=torch.float32) * self.p_bin_step_mm,
        )
        bin_mask = torch.zeros(self.n_p_bins)
        bin_mask[0] = -1e4
        self.register_buffer("p_bin_mask", bin_mask)

    def decode_p(
        self,
        context,
        active_count,
        p_teacher=None,
        teacher_forcing_ratio=0.0,
    ):
        batch_size = context.shape[0]
        hidden = torch.tanh(self.gru_initial_state(context))
        previous_p_mm = torch.zeros(
            batch_size, 1, device=context.device, dtype=context.dtype
        )
        cumulative_mm = torch.zeros_like(previous_p_mm)
        active_count = active_count.view(-1, 1).clamp(0, N_Y)
        position_embeddings = self.position_embedding(
            torch.arange(N_Y, device=context.device)
        )

        all_logits = []
        for step in range(N_Y):
            position_embedding = position_embeddings[step].unsqueeze(0).expand(
                batch_size, -1
            )
            remaining_fraction = (
                (active_count - step).clamp_min(0) / active_count.clamp_min(1)
            ).float()
            active = (step < active_count).float()

            step_input = torch.cat(
                [
                    context,
                    position_embedding,
                    previous_p_mm / self.previous_p_scale_mm,
                    cumulative_mm / self.cumulative_scale_mm,
                    remaining_fraction,
                    active,
                ],
                dim=1,
            )
            hidden = self.p_gru(step_input, hidden)
            logits = self.p_head(hidden) + self.p_bin_mask
            all_logits.append(logits)

            predicted_mm = self.p_bin_values_mm[logits.argmax(dim=1)].unsqueeze(1)
            predicted_mm = predicted_mm * active

            if p_teacher is not None and teacher_forcing_ratio > 0.0:
                teacher_mm = (
                    p_teacher[:, step : step + 1] * self.p_std_mm[:, step : step + 1]
                    + self.p_mean_mm[:, step : step + 1]
                )
                use_teacher = (
                    torch.rand(batch_size, 1, device=context.device)
                    < teacher_forcing_ratio
                )
                next_p_mm = torch.where(use_teacher, teacher_mm, predicted_mm.detach())
            else:
                next_p_mm = predicted_mm

            previous_p_mm = next_p_mm * active
            cumulative_mm = cumulative_mm + previous_p_mm

        return torch.stack(all_logits, dim=1)

    def forward(
        self,
        x_cat,
        x_num,
        p_transition_idx=None,
        p_teacher=None,
        active_count=None,
        teacher_forcing_ratio=0.0,
    ):
        context = self.encode(x_cat, x_num)
        n_rows_logits = self.head_n_rows(context)

        if active_count is None:
            total_rows = n_rows_logits.argmax(dim=1).clamp(1, N_Y + 1)
            active_count = (total_rows - 1).clamp(0, N_Y)

        p_logits = self.decode_p(
            context=context,
            active_count=active_count,
            p_teacher=p_teacher,
            teacher_forcing_ratio=teacher_forcing_ratio,
        )
        p_mode_mm = self.p_bin_values_mm[p_logits.argmax(dim=-1)]
        p_mode_mm = p_mode_mm * (torch.arange(N_Y, device=context.device)[None, :] < active_count[:, None]).float()
        p_values_z = (p_mode_mm - self.p_mean_mm) / self.p_std_mm
        stiffener_values = self.head_stiffener_value(context)

        return {
            "standard_logits": self.head_standard(context),
            "bolt_logits": self.head_bolt(context),
            "slip_critical_logit": self.head_slip_critical(context).squeeze(-1),
            "n_rows_logits": n_rows_logits,
            "reg_always": self.head_reg_always(context),
            "masked_value": torch.cat([p_values_z, stiffener_values], dim=1),
            "masked_presence_logit": self.head_masked_presence(context),
            "p_logits": p_logits,
            "p_mode_mm": p_mode_mm,
        }
