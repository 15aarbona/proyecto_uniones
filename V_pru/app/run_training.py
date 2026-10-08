"""Entrenamiento inicial real desde V_pru/app/data/data_final.csv (sep=';')."""
import store

CSV_PATH = store.DATA_DIR / "data_final.csv"

meta = store.train_final(CSV_PATH, epochs=200, lr=2e-3)
print("\n=== RESULTADO ===")
print("filas de test:", meta.get("metrics", {}).get("n_test"))
print("classification_accuracy:")
for k, v in meta["metrics"]["classification_accuracy"].items():
    print(f"  {k}: {v:.4f}")
print("\nregresión (resumen):")
for row in meta["metrics"]["regression_table"]:
    print(f"  {row['Variable']:6s} MAE={row['MAE (mm)']:8.2f}  %<=5mm={row['% <= 5mm (Taller)']:5.1f}")
