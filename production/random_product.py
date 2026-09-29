import numpy as np
import pandas as pd

np.random.seed(42)

# Perfiles de viga (Nombre, Tipo, d, bf, tw, tf)
beams = [
    ("IPE200", "IPE", 200.0, 100.0, 5.6, 8.5),
    ("IPE240", "IPE", 240.0, 120.0, 6.2, 9.8),
    ("IPE300", "IPE", 300.0, 150.0, 7.1, 10.7),
    ("IPE360", "IPE", 360.0, 170.0, 8.0, 12.7),
    ("IPE400", "IPE", 400.0, 180.0, 8.6, 13.5),
    ("HEA200", "HEA", 190.0, 200.0, 6.5, 10.0),
    ("HEA260", "HEA", 250.0, 260.0, 7.5, 12.5),
    ("HEA300", "HEA", 290.0, 300.0, 8.5, 14.0),
    ("HEB240", "HEB", 240.0, 240.0, 10.0, 17.0),
    ("HEB300", "HEB", 300.0, 300.0, 11.0, 19.0),
]

# Perfiles de columna
columns = [
    ("HEB240", "HEB", 240.0, 240.0, 10.0, 17.0),
    ("HEB280", "HEB", 280.0, 280.0, 10.5, 18.0),
    ("HEB320", "HEB", 320.0, 300.0, 11.5, 20.5),
    ("HEA300", "HEA", 290.0, 300.0, 8.5, 14.0),
    ("HEA400", "HEA", 390.0, 300.0, 11.0, 19.0),
    ("HEB400", "HEB", 400.0, 300.0, 13.5, 24.0),
]

# Grados de acero y tornillos
steel_grades = {"S275JR": (275.0, 430.0), "S355JR": (355.0, 490.0)}

bolt_classes = {
    "8.8": (640.0, 800.0, 480.0),
    "10.9": (900.0, 1000.0, 500.0),
    "A325M": (660.0, 830.0, 372.0),
}

data = []
for i in range(1, 101):
    b = beams[np.random.randint(0, len(beams))]
    c = columns[np.random.randint(0, len(columns))]
    sg_name = np.random.choice(list(steel_grades.keys()))
    sg_val = steel_grades[sg_name]
    bc_name = np.random.choice(list(bolt_classes.keys()))
    bc_val = bolt_classes[bc_name]

    m_cap = round(float(np.random.uniform(30, 450)), 2)
    v_cap = round(float(np.random.uniform(50, 500)), 2)
    a_cap = round(float(np.random.choice([0.0, 0.0, 0.0, 15.0, 30.0, 50.0])), 2)

    data.append({
        "UNICODE": f"U{i:04d}",
        "BEAM": b[0],
        "COLUMN": c[0],
        "BEAM_type": b[1],
        "COLUMN_type": c[1],
        "BEAM_d_mm": b[2],
        "BEAM_bf_mm": b[3],
        "BEAM_tw_mm": b[4],
        "BEAM_tf_mm": b[5],
        "COLUMN_d_mm": c[2],
        "COLUMN_bf_mm": c[3],
        "COLUMN_tw_mm": c[4],
        "COLUMN_tf_mm": c[5],
        "grado_acero": sg_name,
        "clase_tornillo": bc_name,
        "fy_acero_mpa": sg_val[0],
        "fu_acero_mpa": sg_val[1],
        "fy_tornillo_mpa": bc_val[0],
        "fu_tornillo_mpa": bc_val[1],
        "fv_tornillo_mpa": bc_val[2],
        "Capacity_Moment": m_cap,
        "Capacity_Shear": v_cap,
        "Capacity_Axial": a_cap,
    })

df = pd.DataFrame(data)
df.to_excel("plantilla_prueba_100_uniones.xlsx", sheet_name="Datos_IA", index=False)
print("Archivo 'plantilla_prueba_100_uniones.xlsx' generado con 100 filas correctamente.")