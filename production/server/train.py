"""
Script de entrenamiento para el modelo de uniones viga-columna.
Lee el dataset, ajusta el preprocesador, entrena la red PyTorch
y guarda model.pt y preprocessor.pkl en server/models/.
"""
import logging
import pickle
from pathlib import Path

import pandas as pd
import torch
from torch.utils.data import DataLoader, random_split

import config
from dataset import ConnectionDataset, Preprocessor
from losses import ConnectionDesignLoss
from model import ConnectionDesignNet
from training import fit

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(config.LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("ai-train")


def train_main(data_path: Path = None, epochs: int = 200, batch_size: int = 32, lr: float = 2e-3):
    # 1. Localizar archivo de datos
    if data_path is None:
        # Busca primero el dataset acumulado; si no existe, busca el dataset base de entrenamiento
        if config.DATASET_PATH.exists():
            data_path = config.DATASET_PATH
        else:
            data_path = config.DATA_DIR / "train_v3.parquet"

    if not data_path.exists():
        raise FileNotFoundError(
            f"No se encontró ningún dataset para entrenar en {data_path}. "
            f"Asegúrate de colocar 'train_v3.parquet' en la carpeta '{config.DATA_DIR}' "
            f"o validar filas desde Excel."
        )

    log.info(f"Cargando datos de entrenamiento desde: {data_path}")
    if data_path.suffix == ".parquet":
        df = pd.read_parquet(data_path)
    else:
        df = pd.read_csv(data_path)

    log.info(f"Dataset cargado correctamente: {len(df)} filas.")

    # 2. Ajustar Preprocesador
    log.info("Ajustando Preprocessor...")
    preprocessor = Preprocessor()
    preprocessor.fit(df)

    # 3. Crear Dataset y Split de datos (80% Train, 20% Val)
    full_dataset = ConnectionDataset(df, preprocessor)
    val_size = max(1, int(len(full_dataset) * 0.2))
    train_size = len(full_dataset) - val_size

    train_ds, val_ds = random_split(
        full_dataset, [train_size, val_size], generator=torch.Generator().manual_seed(42)
    )

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    # 4. Inicializar Modelo
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    num_cont = len(config.NUMERIC_FEATURES)

    model = ConnectionDesignNet(
        cat_cardinalities=preprocessor.cat_cardinalities,
        num_continuous=num_cont,
        n_standard_classes=preprocessor.n_standard_classes,
    ).to(device)

    # 5. Configurar Función de Pérdida con Pesos de Clase
    w_alma = preprocessor.count_class_weights.get(config.TARGET_CLS_N_ALMA)
    w_cant = preprocessor.count_class_weights.get(config.TARGET_CLS_N_CANTONERA)

    criterion = ConnectionDesignLoss(
        n_alma_weights=w_alma,
        n_cantonera_weights=w_cant,
    ).to(device)

    # 6. Bucle de Entrenamiento
    log.info(f"Iniciando entrenamiento en dispositivo '{device}' ({epochs} épocas)...")
    history = fit(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        criterion=criterion,
        device=device,
        epochs=epochs,
        lr=lr,
        verbose=True,
    )

    # 7. Guardar Pesos y Preprocesador
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)

    log.info(f"Guardando preprocesador en {config.PREPROCESSOR_PATH}...")
    with open(config.PREPROCESSOR_PATH, "wb") as f:
        pickle.dump(preprocessor, f)

    log.info(f"Guardando pesos del modelo en {config.MODEL_PATH}...")
    torch.save(model.state_dict(), config.MODEL_PATH)

    log.info("Entrenamiento y guardado finalizados con éxito.")


if __name__ == "__main__":
    train_main()