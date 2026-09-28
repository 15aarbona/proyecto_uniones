"""
GUI de USUARIO (tkinter, escritorio, sin servidor / sin puertos) — obtener
predicciones a partir de un CSV o Excel tipo fictional.csv.

Admite cargar el fichero de entrada en CSV (.csv) o Excel (.xlsx/.xls), y
descargar los resultados en CSV o Excel, a elección del usuario. El dataset
global que se guarda internamente para reentrenar sigue en parquet (eso no
cambia, es independiente del formato de entrada/salida que vea el usuario).

Ejecutar con:
    python predict_app_tk.py
"""
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import pandas as pd

import store
from core.config import RAW_INPUT_COLUMNS, P_COLUMNS, GEOM_COLUMNS, CATALOGO_BOLT
from core.geometry import gaps_from_p, p_from_named, assemble_from_named
from gui_common import DataFrameTable, run_in_thread


def read_table(path: str) -> pd.DataFrame:
    """Lee un CSV o un Excel (.xlsx/.xls) según la extensión."""
    ext = Path(path).suffix.lower()
    if ext in (".xlsx", ".xls", ".xlsm"):
        return pd.read_excel(path)
    return pd.read_csv(path)


def write_table(df: pd.DataFrame, path: str) -> None:
    """Guarda un DataFrame como CSV o Excel (.xlsx) según la extensión elegida."""
    ext = Path(path).suffix.lower()
    if ext in (".xlsx", ".xlsm"):
        df.to_excel(path, index=False)
    elif ext == ".xls":
        # pandas ya no soporta escribir .xls (xlwt discontinuado); se guarda como .xlsx
        path = str(Path(path).with_suffix(".xlsx"))
        df.to_excel(path, index=False)
    else:
        df.to_csv(path, index=False)


class PredictApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Predicción de diseño de conexiones")
        self.geometry("1250x760")

        self.input_df = None
        self.result_df = None
        self.feats_df = None
        self.validated = set()  # índices (0..n-1) marcados como validados

        self._build_widgets()
        self._refresh_status()

    # ------------------------------------------------------------------
    def _build_widgets(self):
        top = ttk.Frame(self, padding=(10, 10, 10, 0))
        top.pack(fill="x")
        self.status_label = ttk.Label(top, text="", justify="left")
        self.status_label.pack(side="left")

        btns = ttk.Frame(self, padding=10)
        btns.pack(fill="x")
        ttk.Button(btns, text="1. Cargar CSV/Excel…", command=self.load_input_file).pack(side="left", padx=3)
        self.predict_btn = ttk.Button(btns, text="2. Predecir", command=self.predict, state="disabled")
        self.predict_btn.pack(side="left", padx=3)
        self.download_btn = ttk.Button(
            btns, text="3. Descargar resultados…", command=self.download_results, state="disabled"
        )
        self.download_btn.pack(side="left", padx=3)
        ttk.Separator(btns, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(btns, text="Marcar todas ✔", command=lambda: self._toggle_all(True)).pack(side="left", padx=3)
        ttk.Button(btns, text="Desmarcar todas", command=lambda: self._toggle_all(False)).pack(side="left", padx=3)
        self.save_btn = ttk.Button(
            btns, text="4. Guardar validadas en el dataset", command=self.save_validated, state="disabled"
        )
        self.save_btn.pack(side="left", padx=3)

        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.pack(fill="x", padx=10)

        hint = ttk.Label(
            self,
            text="Tras predecir: doble clic en «Validar» marca la fila como correcta; doble clic en cualquier otra celda la edita (Enter = aceptar, Esc = cancelar).",
            foreground="#555",
        )
        hint.pack(anchor="w", padx=10, pady=(2, 0))

        self.table = DataFrameTable(self, padding=10)
        self.table.pack(fill="both", expand=True, padx=10, pady=10)
        self.table.tree.bind("<Double-1>", self._on_cell_double_click)

        self.info_label = ttk.Label(self, text="", foreground="#555")
        self.info_label.pack(fill="x", padx=10, pady=(0, 10))

    # ------------------------------------------------------------------
    def _refresh_status(self):
        meta = store.load_metadata()
        if meta is None:
            self.status_label.config(
                text="⚠️  No hay ningún modelo entrenado todavía. Pide al administrador que "
                     "entrene el modelo inicial (admin_app_tk.py)."
            )
        else:
            acc = meta["metrics"]["classification_accuracy"]
            acc_txt = "  ".join(f"{k}={v:.2f}" for k, v in acc.items())
            self.status_label.config(
                text=(
                    f"Modelo actualizado: {meta['trained_at']}   |   "
                    f"Filas en dataset: {meta['n_rows_dataset']}   |   Accuracy: {acc_txt}"
                )
            )

    # ------------------------------------------------------------------
    def load_input_file(self):
        path = filedialog.askopenfilename(
            filetypes=[
                ("CSV o Excel", "*.csv *.xlsx *.xls *.xlsm"),
                ("CSV", "*.csv"),
                ("Excel", "*.xlsx *.xls *.xlsm"),
            ]
        )
        if not path:
            return
        try:
            df = read_table(path)
        except Exception as e:
            messagebox.showerror("Error al leer el fichero", str(e))
            return

        missing = [c for c in RAW_INPUT_COLUMNS if c not in df.columns]
        if missing:
            messagebox.showerror("Faltan columnas", f"Faltan columnas obligatorias en el fichero:\n{missing}")
            return

        self.input_df = df
        self.result_df = None
        self.feats_df = None
        self.validated = set()
        self.table.set_dataframe(df)
        self.predict_btn.config(state="normal")
        self.download_btn.config(state="disabled")
        self.save_btn.config(state="disabled")
        self.info_label.config(text=f"{len(df)} filas cargadas de {path}")

    def predict(self):
        if store.load_metadata() is None:
            messagebox.showerror("Sin modelo", "No hay ningún modelo entrenado todavía.")
            return
        self.predict_btn.config(state="disabled")
        self.progress.start(10)
        self.info_label.config(text="Calculando predicciones…")
        run_in_thread(
            lambda: store.predict_df(self.input_df),
            self._on_predict_done,
            self._on_predict_error,
            root=self,
        )

    def _on_predict_done(self, payload):
        self.progress.stop()
        result_df, feats_df = payload
        self.result_df = result_df.reset_index(drop=True)
        self.feats_df = feats_df.reset_index(drop=True)
        self.validated = set()

        display = self.result_df.copy()
        display.insert(0, "Validar", "☐")
        self.table.set_dataframe(display)

        self.predict_btn.config(state="normal")
        self.download_btn.config(state="normal")
        self.save_btn.config(state="normal")
        self.info_label.config(
            text=f"Predicción completa para {len(self.result_df)} filas "
                 f"(incluye p1..p12 reconstruidas). Doble clic en una celda para corregir su valor y en «Validar» para marcar la fila."
        )

    def _on_predict_error(self, err):
        self.progress.stop()
        self.predict_btn.config(state="normal")
        self.info_label.config(text="")
        messagebox.showerror("Error al predecir", str(err))

    # ------------------------------------------------------------------
    # Columnas que no se editan a mano: identificadores y derivadas por aritmética
    NON_EDITABLE = {"UNICODE", "BEAM", "COLUMN", "Hole", "num_filas_tornillos", "tiene_cantonera"}
    TEXT_COLUMNS = {"DrawingCode", "Bolt", "SlipCritical"}

    def _on_cell_double_click(self, event):
        tree = self.table.tree
        if self.result_df is None:
            return
        if tree.identify_region(event.x, event.y) != "cell":
            return
        col_id = tree.identify_column(event.x)  # '#1', '#2', ...
        row_id = tree.identify_row(event.y)
        if not row_id:
            return
        col_name = tree["columns"][int(col_id.replace("#", "")) - 1]

        if col_name == "Validar":
            idx = int(row_id)
            if idx in self.validated:
                self.validated.discard(idx)
                tree.set(row_id, "Validar", "☐")
            else:
                self.validated.add(idx)
                tree.set(row_id, "Validar", "☑")
            return

        if col_name in self.NON_EDITABLE:
            self.info_label.config(text=f"«{col_name}» no es editable (identificador o valor derivado automáticamente).")
            return
        self._start_cell_edit(row_id, col_id, col_name)

    def _start_cell_edit(self, row_id, col_id, col_name):
        tree = self.table.tree
        bbox = tree.bbox(row_id, col_id)
        if not bbox:
            return
        x, y, w, h = bbox
        var = tk.StringVar(value=str(tree.set(row_id, col_name)))
        entry = ttk.Entry(tree, textvariable=var)
        entry.place(x=x, y=y, width=w, height=h)
        entry.focus_set()
        entry.select_range(0, "end")
        done = {"v": False}

        def finish(commit):
            if done["v"]:
                return
            done["v"] = True
            new_text = var.get().strip()
            entry.destroy()
            if commit:
                self._apply_edit(int(row_id), col_name, new_text)

        entry.bind("<Return>", lambda e: finish(True))
        entry.bind("<FocusOut>", lambda e: finish(True))
        entry.bind("<Escape>", lambda e: finish(False))

    def _apply_edit(self, idx, col_name, text):
        """Valida y aplica una edición manual, y recalcula lo que dependa de ella."""
        df = self.result_df
        try:
            if col_name == "Bolt":
                t = text.upper().replace(" ", "")
                nominal = int(t[1:] if t.startswith("M") else t)
                if nominal not in CATALOGO_BOLT:
                    raise ValueError(f"Bolt debe ser uno de {['M%d' % b for b in CATALOGO_BOLT]}")
                value = f"M{nominal}"
            elif col_name == "SlipCritical":
                value = text.upper()
                if value not in ("YES", "NO"):
                    raise ValueError("SlipCritical debe ser YES o NO")
            elif col_name in self.TEXT_COLUMNS:
                if not text:
                    raise ValueError(f"{col_name} no puede estar vacío")
                value = text
            else:
                value = float(text.replace(",", "."))
                if value < 0:
                    raise ValueError("El valor no puede ser negativo")
        except ValueError as e:
            messagebox.showerror("Valor no válido", str(e))
            return

        if df.at[idx, col_name] == value:
            return
        df.at[idx, col_name] = value
        self._recompute_derived(idx, col_name)
        self._refresh_row(idx)
        self.info_label.config(text=f"Fila {idx + 1}: «{col_name}» editado. Recuerda marcarla como validada para guardarla.")

    def _recompute_derived(self, idx, edited_col):
        """Mantiene coherentes p1..p12 <-> E-S/D_i/I-C/C_i/E-C y Hole/num_filas/cantonera."""
        df, feats = self.result_df, self.feats_df
        if edited_col in P_COLUMNS:
            row = pd.DataFrame([{
                **{c: df.at[idx, c] for c in P_COLUMNS},
                "e": df.at[idx, "e"], "d": df.at[idx, "d"],
                "BEAM_d_mm": feats.at[idx, "BEAM_d_mm"],
            }])
            geom = gaps_from_p(row).iloc[0]
            for c in GEOM_COLUMNS:
                df.at[idx, c] = 0.0 if pd.isna(geom[c]) else float(geom[c])
        elif edited_col in GEOM_COLUMNS:
            p = p_from_named(df.loc[[idx], GEOM_COLUMNS]).iloc[0]
            for c in P_COLUMNS:
                df.at[idx, c] = float(p[c])

        bolt_nominal = int(str(df.at[idx, "Bolt"]).replace("M", ""))
        derived = assemble_from_named(df.loc[[idx], GEOM_COLUMNS], [bolt_nominal]).iloc[0]
        df.at[idx, "Hole"] = derived["Hole"]
        df.at[idx, "num_filas_tornillos"] = derived["num_filas_tornillos"]
        df.at[idx, "tiene_cantonera"] = bool(derived["tiene_cantonera"])

    def _refresh_row(self, idx):
        tree = self.table.tree
        iid = str(idx)
        for c in tree["columns"]:
            if c == "Validar":
                continue
            v = self.result_df.at[idx, c]
            tree.set(iid, c, "" if pd.isna(v) else v)

    def _toggle_all(self, value):
        if self.result_df is None:
            return
        tree = self.table.tree
        for iid in tree.get_children():
            idx = int(iid)
            if value:
                self.validated.add(idx)
                tree.set(iid, "Validar", "☑")
            else:
                self.validated.discard(idx)
                tree.set(iid, "Validar", "☐")

    # ------------------------------------------------------------------
    def download_results(self):
        if self.result_df is None:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")],
        )
        if not path:
            return
        try:
            write_table(self.result_df, path)
        except Exception as e:
            messagebox.showerror("Error al guardar", str(e))
            return
        messagebox.showinfo("Guardado", f"Resultados guardados en:\n{path}")

    def save_validated(self):
        if not self.validated:
            messagebox.showwarning("Sin selección", "No has marcado ninguna fila como validada.")
            return
        idx = sorted(self.validated)
        design_cols = [c for c in self.result_df.columns if c not in ("UNICODE", "BEAM", "COLUMN")]
        try:
            rows = store.build_dataset_rows(
                self.feats_df.loc[idx].reset_index(drop=True),
                self.result_df.loc[idx, design_cols].reset_index(drop=True),
            )
            new_size = store.append_validated_rows(rows)
        except Exception as e:
            messagebox.showerror("Error al guardar", str(e))
            return
        messagebox.showinfo(
            "Guardado",
            f"{len(idx)} fila(s) añadidas al dataset global.\n"
            f"El dataset global tiene ahora {new_size} filas.\n\n"
            "Pide al administrador que reentrene cuando quiera incorporar estos casos al modelo.",
        )
        self._refresh_status()


if __name__ == "__main__":
    PredictApp().mainloop()
