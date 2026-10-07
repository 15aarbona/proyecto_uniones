"""Entrenamiento inicial real con la estructura v4."""
import store

meta = store.train_initial(
    test_path=r"C:\Users\jabal\OtrosProyectos\proyecto_uniones\data\test_v2.parquet",
    train_path=r"C:\Users\jabal\OtrosProyectos\proyecto_uniones\data\train_v2.parquet",
    epochs=200, lr=2e-3,
)
print("\n=== RESULTADO ===")
print("época mejor:", meta.get("metrics", {}).get("n_test"), "filas de test")
print("classification_accuracy:")
for k, v in meta["metrics"]["classification_accuracy"].items():
    print(f"  {k}: {v:.4f}")
print("\nregresión (resumen):")
for row in meta["metrics"]["regression_table"]:
    print(f"  {row['Variable']:6s} MAE={row['MAE (mm)']:8.2f}  %<=5mm={row['% <= 5mm (Taller)']:5.1f}")
