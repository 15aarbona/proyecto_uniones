"""
GUI de ADMINISTRADOR (tkinter, escritorio, sin servidor / sin puertos) —
entrenar el modelo por primera vez, reentrenar con el dataset acumulado,
y ver estado / historial / dataset global.

Ejecutar con:
    python admin_app_tk.py
"""
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import pandas as pd

import store
from gui_common import DataFrameTable, run_in_thread


class AdminApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Administración — modelo de diseño de conexiones")
        self.geometry("1350x820")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        self.tab_status = ttk.Frame(nb)
        self.tab_initial = ttk.Frame(nb)
        self.tab_retrain = ttk.Frame(nb)
        self.tab_dataset = ttk.Frame(nb)
        nb.add(self.tab_status, text="📊 Estado")
        nb.add(self.tab_initial, text="🆕 Entrenamiento inicial")
        nb.add(self.tab_retrain, text="🔁 Reentrenar")
        nb.add(self.tab_dataset, text="🗂️ Dataset global")

        self._build_status_tab()
        self._build_initial_tab()
        self._build_retrain_tab()
        self._build_dataset_tab()
        self.refresh_all()

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------
    def _build_status_tab(self):
        f = self.tab_status
        top = ttk.Frame(f, padding=10)
        top.pack(fill="x")
        self.status_text = tk.Text(top, height=5, wrap="word", state="disabled", relief="flat",
                                    background=self.cget("background"))
        self.status_text.pack(fill="x")

        ttk.Label(f, text="Accuracy de clasificación (test del último (re)entreno):").pack(anchor="w", padx=10)
        self.acc_table = DataFrameTable(f, padding=(10, 0, 10, 10), max_rows=20)
        self.acc_table.pack(fill="x", padx=10)
        self.acc_table.configure(height=90)

        ttk.Label(f, text="Error de regresión por variable (test):").pack(anchor="w", padx=10)
        self.reg_table = DataFrameTable(f, padding=(10, 0, 10, 10))
        self.reg_table.pack(fill="both", expand=True, padx=10)

        ttk.Label(f, text="Historial de entrenamientos:").pack(anchor="w", padx=10, pady=(8, 0))
        self.hist_table = DataFrameTable(f, padding=10)
        self.hist_table.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        ttk.Button(f, text="🔄 Refrescar", command=self.refresh_all).pack(pady=6)

    def refresh_all(self):
        meta = store.load_metadata()
        self.status_text.configure(state="normal")
        self.status_text.delete("1.0", "end")
        if meta is None:
            self.status_text.insert("end", "No se ha entrenado ningún modelo todavía.")
            self.acc_table.set_dataframe(pd.DataFrame())
            self.reg_table.set_dataframe(pd.DataFrame())
        else:
            self.status_text.insert(
                "end",
                f"Última actualización: {meta['trained_at']}\n"
                f"Modo: {meta['mode']}    Épocas: {meta['epochs']}    Learning rate: {meta['lr']}\n"
                f"Filas en el dataset global: {meta['n_rows_dataset']}\n",
            )
            acc_df = pd.DataFrame([meta["metrics"]["classification_accuracy"]]).T.reset_index()
            acc_df.columns = ["variable", "accuracy"]
            self.acc_table.set_dataframe(acc_df)
            self.reg_table.set_dataframe(pd.DataFrame(meta["metrics"]["regression_table"]))
        self.status_text.configure(state="disabled")

        hist = store.load_history()
        rows = [
            {
                "fecha": h["trained_at"], "modo": h["mode"], "epochs": h["epochs"], "lr": h["lr"],
                "n_filas_dataset": h["n_rows_dataset"],
                "acc_DrawingCode": round(h["metrics"]["classification_accuracy"].get("DrawingCode", 0), 3),
                "acc_Bolt": round(h["metrics"]["classification_accuracy"].get("Bolt", 0), 3),
                "acc_SlipCritical": round(h["metrics"]["classification_accuracy"].get("SlipCritical", 0), 3),
            }
            for h in hist
        ]
        self.hist_table.set_dataframe(pd.DataFrame(rows))
        self._refresh_dataset_tab()

    # ------------------------------------------------------------------
    # Entrenamiento inicial
    # ------------------------------------------------------------------
    def _build_initial_tab(self):
        f = self.tab_initial
        pad = dict(padx=10, pady=6)

        note = ttk.Label(
            f,
            text=(
                "Entrena el modelo por primera vez a partir de train.parquet / test.parquet\n"
                "(el dataset \"rico\", con p1..p12, DrawingCode, Bolt, etc.). Al terminar se guarda\n"
                "el modelo Y se crea el dataset global (con la geometría E-S/D_i/I-C/C_i/E-C ya\n"
                "calculada) que se usará en los reentrenos futuros.\n"
                "⚠️ Repetirlo SOBRESCRIBE el modelo y el dataset global (usa «Reentrenar» para\n"
                "incorporar filas nuevas sin perder lo acumulado)."
            ),
            foreground="#555", justify="left",
        )
        note.grid(row=0, column=0, columnspan=3, sticky="w", **pad)

        ttk.Label(f, text="test.parquet (obligatorio):").grid(row=1, column=0, sticky="w", **pad)
        self.test_path_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.test_path_var, width=70).grid(row=1, column=1, **pad)
        ttk.Button(f, text="Elegir…", command=self._pick_test).grid(row=1, column=2, **pad)

        ttk.Label(f, text="train.parquet (opcional):").grid(row=2, column=0, sticky="w", **pad)
        self.train_path_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.train_path_var, width=70).grid(row=2, column=1, **pad)
        ttk.Button(f, text="Elegir…", command=self._pick_train).grid(row=2, column=2, **pad)

        ttk.Label(f, text="Épocas:").grid(row=3, column=0, sticky="w", **pad)
        self.init_epochs_var = tk.IntVar(value=150)
        ttk.Spinbox(f, from_=1, to=2000, textvariable=self.init_epochs_var, width=10).grid(
            row=3, column=1, sticky="w", **pad
        )

        ttk.Label(f, text="Learning rate:").grid(row=4, column=0, sticky="w", **pad)
        self.init_lr_var = tk.DoubleVar(value=2e-3)
        ttk.Entry(f, textvariable=self.init_lr_var, width=10).grid(row=4, column=1, sticky="w", **pad)

        self.init_btn = ttk.Button(f, text="🚀 Entrenar modelo inicial", command=self._run_initial)
        self.init_btn.grid(row=5, column=0, **pad)
        self.init_progress = ttk.Progressbar(f, mode="indeterminate", length=300)
        self.init_progress.grid(row=5, column=1, sticky="w", **pad)

        self.init_status = ttk.Label(f, text="", foreground="#555")
        self.init_status.grid(row=6, column=0, columnspan=3, sticky="w", **pad)

    def _pick_test(self):
        p = filedialog.askopenfilename(filetypes=[("Parquet", "*.parquet")])
        if p:
            self.test_path_var.set(p)

    def _pick_train(self):
        p = filedialog.askopenfilename(filetypes=[("Parquet", "*.parquet")])
        if p:
            self.train_path_var.set(p)

    def _run_initial(self):
        test_path = self.test_path_var.get().strip()
        if not test_path:
            messagebox.showerror("Falta test.parquet", "Selecciona el fichero test.parquet.")
            return
        if store.model_exists():
            if not messagebox.askyesno(
                "Sobrescribir modelo",
                "Ya existe un modelo entrenado. Esto SOBRESCRIBE el modelo y el dataset global "
                "(perderás las filas validadas acumuladas desde el último entrenamiento inicial).\n\n"
                "¿Continuar?",
            ):
                return

        train_path = self.train_path_var.get().strip() or None
        epochs = int(self.init_epochs_var.get())
        lr = float(self.init_lr_var.get())

        self.init_btn.config(state="disabled")
        self.init_progress.start(10)
        self.init_status.config(text=f"Entrenando {epochs} épocas… puede tardar varios minutos, no cierres la ventana.")

        run_in_thread(
            lambda: store.train_initial(test_path=test_path, train_path=train_path, epochs=epochs, lr=lr),
            self._on_initial_done,
            self._on_initial_error,
            root=self,
        )

    def _on_initial_done(self, meta):
        self.init_progress.stop()
        self.init_btn.config(state="normal")
        self.init_status.config(text=f"Listo. Dataset global: {meta['n_rows_dataset']} filas.")
        messagebox.showinfo(
            "Entrenamiento completado",
            f"Modelo inicial guardado.\nDataset global: {meta['n_rows_dataset']} filas.",
        )
        self.refresh_all()

    def _on_initial_error(self, err):
        self.init_progress.stop()
        self.init_btn.config(state="normal")
        self.init_status.config(text="Error durante el entrenamiento.")
        messagebox.showerror("Error entrenando", str(err))

    # ------------------------------------------------------------------
    # Reentrenar
    # ------------------------------------------------------------------
    def _build_retrain_tab(self):
        f = self.tab_retrain
        pad = dict(padx=10, pady=6)

        note = ttk.Label(
            f,
            text=(
                "Reentrena el modelo DESDE CERO usando todo el dataset global acumulado\n"
                "(el del entrenamiento inicial + las filas nuevas validadas por los usuarios).\n"
                "El modelo se sobrescribe solo si el entrenamiento termina sin errores."
            ),
            foreground="#555", justify="left",
        )
        note.grid(row=0, column=0, columnspan=3, sticky="w", **pad)

        self.retrain_info = ttk.Label(f, text="", font=("", 10, "bold"))
        self.retrain_info.grid(row=1, column=0, columnspan=3, sticky="w", **pad)

        ttk.Label(f, text="Épocas:").grid(row=2, column=0, sticky="w", **pad)
        self.re_epochs_var = tk.IntVar(value=80)
        ttk.Spinbox(f, from_=1, to=2000, textvariable=self.re_epochs_var, width=10).grid(
            row=2, column=1, sticky="w", **pad
        )

        ttk.Label(f, text="Learning rate:").grid(row=3, column=0, sticky="w", **pad)
        self.re_lr_var = tk.DoubleVar(value=1e-3)
        ttk.Entry(f, textvariable=self.re_lr_var, width=10).grid(row=3, column=1, sticky="w", **pad)

        self.re_btn = ttk.Button(f, text="🔁 Reentrenar con el dataset global", command=self._run_retrain)
        self.re_btn.grid(row=4, column=0, **pad)
        self.re_progress = ttk.Progressbar(f, mode="indeterminate", length=300)
        self.re_progress.grid(row=4, column=1, sticky="w", **pad)

        self.re_status = ttk.Label(f, text="", foreground="#555")
        self.re_status.grid(row=5, column=0, columnspan=3, sticky="w", **pad)

    def _run_retrain(self):
        global_df = store.load_global_dataset()
        if global_df is None:
            messagebox.showerror("Sin dataset", "No hay dataset global. Entrena primero el modelo inicial.")
            return

        epochs = int(self.re_epochs_var.get())
        lr = float(self.re_lr_var.get())

        self.re_btn.config(state="disabled")
        self.re_progress.start(10)
        self.re_status.config(text=f"Reentrenando {epochs} épocas…")

        run_in_thread(
            lambda: store.retrain(epochs=epochs, lr=lr),
            self._on_retrain_done,
            self._on_retrain_error,
            root=self,
        )

    def _on_retrain_done(self, meta):
        self.re_progress.stop()
        self.re_btn.config(state="normal")
        self.re_status.config(text=f"Listo. Dataset global: {meta['n_rows_dataset']} filas.")
        messagebox.showinfo(
            "Reentrenamiento completado",
            f"Modelo reentrenado y guardado.\nDataset global: {meta['n_rows_dataset']} filas.",
        )
        self.refresh_all()

    def _on_retrain_error(self, err):
        self.re_progress.stop()
        self.re_btn.config(state="normal")
        self.re_status.config(text="Error durante el reentrenamiento.")
        messagebox.showerror("Error reentrenando", str(err))

    # ------------------------------------------------------------------
    # Dataset global
    # ------------------------------------------------------------------
    def _build_dataset_tab(self):
        f = self.tab_dataset
        top = ttk.Frame(f, padding=10)
        top.pack(fill="x")
        self.dataset_info = ttk.Label(top, text="")
        self.dataset_info.pack(side="left")
        ttk.Button(top, text="⬇️ Exportar…", command=self._export_dataset).pack(side="right")

        self.dataset_table = DataFrameTable(f, padding=10)
        self.dataset_table.pack(fill="both", expand=True, padx=10, pady=10)

    def _refresh_dataset_tab(self):
        df = store.load_global_dataset()
        if df is None:
            self.dataset_info.config(text="No hay dataset global todavía.")
            self.dataset_table.set_dataframe(pd.DataFrame())
        else:
            self.dataset_info.config(
                text=f"Filas: {len(df)}   |   Columnas: {len(df.columns)}   (mostrando las últimas 200)"
            )
            self.dataset_table.set_dataframe(df.tail(200).reset_index(drop=True))

    def _export_dataset(self):
        # Nota: el dataset global se sigue guardando internamente en parquet
        # (model_store/global_dataset.parquet). Esto es solo una exportación de
        # lectura, a elección del usuario, para inspeccionarlo fuera de la app.
        df = store.load_global_dataset()
        if df is None:
            messagebox.showwarning("Sin datos", "No hay dataset global todavía.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")],
        )
        if not path:
            return
        try:
            if Path(path).suffix.lower() in (".xlsx", ".xlsm", ".xls"):
                df.to_excel(path, index=False)
            else:
                df.to_csv(path, index=False)
        except Exception as e:
            messagebox.showerror("Error al exportar", str(e))
            return
        messagebox.showinfo("Exportado", f"Guardado en:\n{path}")


if __name__ == "__main__":
    AdminApp().mainloop()
