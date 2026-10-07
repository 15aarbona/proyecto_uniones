"""
Modelo para el diseño de uniones atornilladas.

Arquitectura
------------

El tronco compartido procesa:

    - variables categóricas mediante embeddings;
    - variables numéricas estandarizadas;
    - bloques residuales completamente conectados.

Salidas globales
----------------

    - standard_logits
    - bolt_logits
    - slip_critical_logit
    - n_alma_logits
    - n_cantonera_logits
    - reg_always

Separaciones p1...p12
---------------------

Las separaciones ya no se predicen con doce salidas posicionales
independientes.

Cada p se obtiene mediante un decodificador compartido condicionado por:

    - representación global de la conexión;
    - transición geométrica correspondiente;
    - posición p1...p12.

Durante entrenamiento puede proporcionarse p_transition_idx calculado
a partir de los conteos reales.

Durante inferencia, si no se proporciona p_transition_idx, el modelo
lo deriva a partir de sus propios conteos predichos.

Rigidizadores
-------------

Los espesores tws, ts, tbs y tst mantienen una cabeza convencional.
"""

import torch
import torch.nn as nn

from .config import (
    CATALOGO_BOLT,
    N_ALMA_CLASSES,
    N_CANTONERA_CLASSES,
    N_P_TRANSITION_CLASSES,
    P_TRANSITION_UNUSED_IDX,
    REGRESSION_ALWAYS,
    STIFFENER_COLUMNS,
    N_Y,
    secuencia_transiciones,
    P_TRANSITION_TO_IDX,
)


N_REG_ALWAYS = len(REGRESSION_ALWAYS)
N_STIFFENERS = len(STIFFENER_COLUMNS)
N_MASKED = N_Y + N_STIFFENERS

TRANSITION_EMBED_DIM = 16
POSITION_EMBED_DIM = 8


def crear_transition_lookup():
    """
    Crea una tabla:

        lookup[n_alma, n_cantonera, posicion_p]

    cuyo contenido es el índice de transición geométrica.

    Las posiciones posteriores al prefijo activo reciben UNUSED.
    """
    lookup = torch.full(
        size=(
            N_ALMA_CLASSES,
            N_CANTONERA_CLASSES,
            N_Y,
        ),
        fill_value=P_TRANSITION_UNUSED_IDX,
        dtype=torch.long,
    )

    for n_alma in range(N_ALMA_CLASSES):
        for n_cantonera in range(N_CANTONERA_CLASSES):
            transiciones = secuencia_transiciones(
                n_alma=n_alma,
                n_cantonera=n_cantonera,
            )

            if len(transiciones) > N_Y:
                raise ValueError(
                    "La combinación "
                    f"n_alma={n_alma}, "
                    f"n_cantonera={n_cantonera} "
                    f"genera {len(transiciones)} transiciones, "
                    f"pero N_Y={N_Y}."
                )

            for posicion, transicion in enumerate(transiciones):
                lookup[
                    n_alma,
                    n_cantonera,
                    posicion,
                ] = P_TRANSITION_TO_IDX[transicion]

    return lookup


class ResNetBlock(nn.Module):
    """
    Bloque residual completamente conectado.
    """

    def __init__(
        self,
        dim,
        dropout=0.1,
    ):
        super().__init__()

        self.fc1 = nn.Linear(dim, dim)
        self.bn1 = nn.BatchNorm1d(dim)

        self.fc2 = nn.Linear(dim, dim)
        self.bn2 = nn.BatchNorm1d(dim)

        self.dropout = nn.Dropout(dropout)
        self.activation = nn.ReLU()

    def forward(self, x):
        residual = x

        out = self.fc1(x)
        out = self.bn1(out)
        out = self.activation(out)
        out = self.dropout(out)

        out = self.fc2(out)
        out = self.bn2(out)

        out = out + residual
        out = self.activation(out)

        return out


class ConnectionDesignNet(nn.Module):
    """
    Red neuronal para predecir el diseño completo de una unión.
    """

    def __init__(
        self,
        cat_cardinalities,
        num_continuous,
        n_standard_classes,
        hidden_dim=192,
        num_blocks=3,
        dropout=0.1,
    ):
        super().__init__()

        self.hidden_dim = hidden_dim

        # ---------------------------------------------------------------
        # Embeddings de entradas categóricas
        # ---------------------------------------------------------------

        self.embedding_dims = [
            min(16, (cardinality + 1) // 2)
            for cardinality in cat_cardinalities
        ]

        self.embeddings = nn.ModuleList(
            [
                nn.Embedding(
                    cardinality,
                    embedding_dim,
                )
                for cardinality, embedding_dim
                in zip(
                    cat_cardinalities,
                    self.embedding_dims,
                )
            ]
        )

        embedding_total_dim = sum(
            self.embedding_dims
        )

        input_dim = (
            embedding_total_dim
            + num_continuous
        )

        # ---------------------------------------------------------------
        # Tronco compartido
        # ---------------------------------------------------------------

        self.input_layer = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
        )

        self.blocks = nn.ModuleList(
            [
                ResNetBlock(
                    dim=hidden_dim,
                    dropout=dropout,
                )
                for _ in range(num_blocks)
            ]
        )

        # ---------------------------------------------------------------
        # Cabezas de clasificación global
        # ---------------------------------------------------------------

        self.head_standard = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Linear(
                64,
                n_standard_classes,
            ),
        )

        self.head_bolt = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Linear(
                64,
                len(CATALOGO_BOLT),
            ),
        )

        self.head_slip_critical = nn.Sequential(
            nn.Linear(hidden_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
        )

        self.head_n_alma = nn.Sequential(
            nn.Linear(hidden_dim, 32),
            nn.ReLU(),
            nn.Linear(
                32,
                N_ALMA_CLASSES,
            ),
        )

        self.head_n_cantonera = nn.Sequential(
            nn.Linear(hidden_dim, 32),
            nn.ReLU(),
            nn.Linear(
                32,
                N_CANTONERA_CLASSES,
            ),
        )

        # ---------------------------------------------------------------
        # Regresiones siempre activas
        # ---------------------------------------------------------------

        self.head_reg_always = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Linear(
                64,
                N_REG_ALWAYS,
            ),
        )

        # ---------------------------------------------------------------
        # Embeddings de la geometría de cada separación
        # ---------------------------------------------------------------

        self.transition_embedding = nn.Embedding(
            N_P_TRANSITION_CLASSES,
            TRANSITION_EMBED_DIM,
        )

        self.p_position_embedding = nn.Embedding(
            N_Y,
            POSITION_EMBED_DIM,
        )

        # ---------------------------------------------------------------
        # Decodificador compartido de las separaciones
        # ---------------------------------------------------------------

        p_decoder_input_dim = (
            hidden_dim
            + TRANSITION_EMBED_DIM
            + POSITION_EMBED_DIM
        )

        self.p_decoder = nn.Sequential(
            nn.Linear(
                p_decoder_input_dim,
                128,
            ),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

        # ---------------------------------------------------------------
        # Rigidizadores
        # ---------------------------------------------------------------

        self.head_stiffener_value = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Linear(
                64,
                N_STIFFENERS,
            ),
        )

        # ---------------------------------------------------------------
        # Presencia auxiliar
        # ---------------------------------------------------------------
        #
        # Se conserva la misma interfaz:
        #   p1...p12 + tws, ts, tbs, tst
        #
        # La presencia de las p NO se utilizará en postproceso.
        # La presencia de los rigidizadores sí.
        # ---------------------------------------------------------------

        self.head_masked_presence = nn.Sequential(
            nn.Linear(hidden_dim, 128),
            nn.ReLU(),
            nn.Linear(
                128,
                N_MASKED,
            ),
        )

        # ---------------------------------------------------------------
        # Tabla de transición derivada de los conteos
        # ---------------------------------------------------------------

        self.register_buffer(
            "transition_lookup",
            crear_transition_lookup(),
        )

    def transition_indices_from_logits(
        self,
        n_alma_logits,
        n_cantonera_logits,
    ):
        """
        Deriva las transiciones a partir de los conteos predichos.

        El argmax no es diferenciable, por lo que esta función se utiliza
        en validación e inferencia, no para proporcionar gradiente a las
        cabezas de conteos.
        """
        n_alma_pred = n_alma_logits.argmax(
            dim=1
        )

        n_cantonera_pred = (
            n_cantonera_logits.argmax(
                dim=1
            )
        )

        return self.transition_lookup[
            n_alma_pred,
            n_cantonera_pred,
        ]

    def forward(
        self,
        x_cat,
        x_num,
        p_transition_idx=None,
    ):
        # ---------------------------------------------------------------
        # Tronco compartido
        # ---------------------------------------------------------------

        embedding_outputs = [
            embedding(x_cat[:, index])
            for index, embedding
            in enumerate(self.embeddings)
        ]

        x = torch.cat(
            embedding_outputs + [x_num],
            dim=1,
        )

        x = self.input_layer(x)

        for block in self.blocks:
            x = block(x)

        # ---------------------------------------------------------------
        # Clasificación de conteos
        # ---------------------------------------------------------------

        n_alma_logits = self.head_n_alma(x)

        n_cantonera_logits = (
            self.head_n_cantonera(x)
        )

        # ---------------------------------------------------------------
        # Transiciones
        # ---------------------------------------------------------------

        if p_transition_idx is None:
            p_transition_idx = (
                self.transition_indices_from_logits(
                    n_alma_logits=n_alma_logits,
                    n_cantonera_logits=(
                        n_cantonera_logits
                    ),
                )
            )

        p_transition_idx = (
            p_transition_idx.long()
        )

        # ---------------------------------------------------------------
        # Contexto por separación
        # ---------------------------------------------------------------

        batch_size = x.shape[0]

        x_repeated = (
            x.unsqueeze(1)
            .expand(
                -1,
                N_Y,
                -1,
            )
        )

        transition_emb = (
            self.transition_embedding(
                p_transition_idx
            )
        )

        position_indices = torch.arange(
            N_Y,
            device=x.device,
        )

        position_emb = (
            self.p_position_embedding(
                position_indices
            )
            .unsqueeze(0)
            .expand(
                batch_size,
                -1,
                -1,
            )
        )

        p_context = torch.cat(
            [
                x_repeated,
                transition_emb,
                position_emb,
            ],
            dim=-1,
        )

        # ---------------------------------------------------------------
        # Valores p y rigidizadores
        # ---------------------------------------------------------------

        p_values = (
            self.p_decoder(p_context)
            .squeeze(-1)
        )

        stiffener_values = (
            self.head_stiffener_value(x)
        )

        masked_value = torch.cat(
            [
                p_values,
                stiffener_values,
            ],
            dim=1,
        )

        return {
            "standard_logits": (
                self.head_standard(x)
            ),
            "bolt_logits": (
                self.head_bolt(x)
            ),
            "slip_critical_logit": (
                self.head_slip_critical(x)
                .squeeze(-1)
            ),
            "n_alma_logits": (
                n_alma_logits
            ),
            "n_cantonera_logits": (
                n_cantonera_logits
            ),
            "reg_always": (
                self.head_reg_always(x)
            ),
            "masked_value": (
                masked_value
            ),
            "masked_presence_logit": (
                self.head_masked_presence(x)
            ),
            "p_transition_idx_used": (
                p_transition_idx
            ),
        }