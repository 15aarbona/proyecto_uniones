"""Entrenamiento desde data_pi_tag.csv (p1..p12 + p1_label..p12_label).

Split pedido: df_train, df_test = train_test_split(df_resultado, test_size=0.2,
random_state=2) (más una val interna del train, semilla 42, para el bucle de fit).
"""
import store

if __name__ == "__main__":
    csv_path = store.DATA_DIR / "data_pi_tag.csv"
    meta = store.train_pi_tag(csv_path, epochs=200, lr=2e-3)

    print("\n=== RESULTADO ===")
    print("filas de test:", meta.get("metrics", {}).get("n_test"))
    print("classification_accuracy:")
    for k, v in meta["metrics"]["classification_accuracy"].items():
        print(f"  {k}: {v:.4f}")
    print("\np_label_accuracy (global):")
    for k, v in meta["metrics"].get("p_label_accuracy", {}).items():
        print(f"  {k}: {v:.4f}")
    print("\np_label_accuracy (solo pasos activos):")
    for k, v in meta["metrics"].get("p_label_accuracy_activos", {}).items():
        print(f"  {k}: {v:.4f}")
    print("\nregresión (resumen):")
    for row in meta["metrics"]["regression_table"]:
        print(f"  {row['Variable']:6s} MAE={row['MAE (mm)']:8.2f}  %<=5mm={row['% <= 5mm (Taller)']:5.1f}")