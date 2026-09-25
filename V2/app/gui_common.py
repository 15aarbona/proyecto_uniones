"""
Utilidades compartidas por las dos GUIs de tkinter:
  - DataFrameTable: envuelve un ttk.Treeview con scrollbars para mostrar un DataFrame.
  - run_in_thread: ejecuta una función pesada (entrenar, predecir...) en un hilo
    aparte para no bloquear la ventana, y entrega el resultado al hilo principal
    de tkinter de forma segura (vía root.after), que es el único que puede tocar
    widgets.
"""
import queue
import threading
import tkinter as tk
from tkinter import ttk

import pandas as pd


class DataFrameTable(ttk.Frame):
    def __init__(self, master, max_rows=2000, **kwargs):
        super().__init__(master, **kwargs)
        self.max_rows = max_rows
        self.df = None

        self.tree = ttk.Treeview(self, show="headings")
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def set_dataframe(self, df: pd.DataFrame):
        self.df = df
        self.tree.delete(*self.tree.get_children())
        if df is None or df.empty:
            self.tree["columns"] = []
            return

        cols = list(df.columns)
        self.tree["columns"] = cols
        for c in cols:
            self.tree.heading(c, text=str(c))
            width = 130 if c != "Validar" else 70
            self.tree.column(c, width=width, anchor="center", stretch=True)

        shown = df.head(self.max_rows)
        for i, (_, row) in enumerate(shown.iterrows()):
            vals = ["" if pd.isna(v) else v for v in row[cols].tolist()]
            self.tree.insert("", "end", iid=str(i), values=vals)

        if len(df) > self.max_rows:
            # fila informativa, no seleccionable/editable
            pass


def run_in_thread(fn, on_done, on_error, root):
    """Ejecuta fn() en un hilo; llama a on_done(resultado) o on_error(excepcion)
    en el hilo principal de tkinter (root) cuando termina."""
    q = queue.Queue()

    def worker():
        try:
            result = fn()
            q.put(("ok", result))
        except Exception as e:  # noqa: BLE001 - queremos capturar cualquier error y mostrarlo
            q.put(("error", e))

    threading.Thread(target=worker, daemon=True).start()

    def poll():
        try:
            status, payload = q.get_nowait()
        except queue.Empty:
            root.after(100, poll)
            return
        if status == "ok":
            on_done(payload)
        else:
            on_error(payload)

    root.after(100, poll)
