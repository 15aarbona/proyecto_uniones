"""Genera artifacts/model_final.pt y artifacts/preprocessor.joblib desde el checkpoint del notebook.

Uso, desde la carpeta PINN/ (con core/ al lado):
    python export_artifacts.py pinn_bolted_connection_best.pth

(el Makefile los copia como weights.pt / preprocessor.joblib en el servidor)
"""
import sys
from pathlib import Path

import joblib
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from core.dataset import Preprocessor  # noqa: E402

src = Path(sys.argv[1] if len(sys.argv) > 1 else "pinn_bolted_connection_best.pth")
ckpt = torch.load(HERE / src, map_location="cpu", weights_only=False)
out = HERE / "artifacts"
out.mkdir(exist_ok=True)

torch.save({
    "model_state_dict": ckpt["model_state_dict"],
    "hyperparameters": ckpt["hyperparameters"],   # hidden_dim, num_res_blocks, dropout_rate, lr
    "epoch": ckpt.get("epoch"),
}, out / "model_final.pt")
joblib.dump(Preprocessor(), out / "preprocessor.joblib")
print("OK ->", out / "model_final.pt", "y", out / "preprocessor.joblib")